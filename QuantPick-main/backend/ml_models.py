"""ML signal layer: XGBoost Buy/Hold/Sell classifier + a compact sequence
model (sklearn gradient-boosting on lagged returns) for short-term direction.
Trained cross-sectionally on the universe's historical bars (walk-forward split)."""
import logging
import numpy as np

logger = logging.getLogger("quantpick.ml")

import numpy as np

def purged_kfold_cv(X, y, n_splits=5, embargo_pct=0.01):
    """Lopez de Prado Purged K-Fold — removes data near train/test boundary to prevent leakage."""
    n = len(X)
    fold_size = n // n_splits
    embargo = int(n * embargo_pct)
    for i in range(n_splits):
        test_start = i * fold_size
        test_end = test_start + fold_size
        test_idx = np.arange(test_start, test_end)
        train_idx = np.concatenate([
            np.arange(0, max(0, test_start - embargo)),
            np.arange(min(n, test_end + embargo), n)
        ])
        if len(train_idx) < 100:
            continue
        yield train_idx, test_idx
SEQ = 10          # lookback window for the direction sequence model


def _series_features(close, volume):
    """Return arrays of engineered features aligned to `close` indices (>=60)."""
    n = len(close)
    logret = np.diff(np.log(np.maximum(close, 1e-6)), prepend=np.log(close[0]))
    feats = np.full((n, 7), np.nan)
    for i in range(60, n):
        w = close[: i + 1]
        sma50 = np.mean(w[-50:]); sma200 = np.mean(w[-200:]) if len(w) >= 200 else np.mean(w)
        # RSI14
        d = np.diff(w[-15:]); g = np.mean(np.clip(d, 0, None)); l = np.mean(np.clip(-d, 0, None))
        rsi = 100 - 100 / (1 + g / (l + 1e-9))
        # MACD hist (approx via EMA diff on last 40)
        seg = w[-40:]
        e12 = seg[-1]; e26 = seg[-1]
        a12, a26 = 2 / 13, 2 / 27
        for x in seg:
            e12 = a12 * x + (1 - a12) * e12
            e26 = a26 * x + (1 - a26) * e26
        macd = (e12 - e26) / w[-1]
        mom1 = w[-1] / w[-21] - 1 if len(w) > 21 else 0
        mom3 = w[-1] / w[-63] - 1 if len(w) > 63 else 0
        vol = np.std(logret[i - 20: i + 1]) * np.sqrt(252)
        vmean = np.mean(volume[max(0, i - 20): i + 1]) + 1
        vz = (volume[i] - vmean) / (np.std(volume[max(0, i - 20): i + 1]) + 1)
        feats[i] = [rsi / 100, macd, mom1, mom3, w[-1] / sma50 - 1, sma50 / sma200 - 1, np.tanh(vz)]
    return feats, logret


class MLEngine:
    def __init__(self):
        self.clf = None       # XGBoost multiclass
        self.dir_model = None  # direction sequence model
        self.trained = False

    def train_and_predict(self, bars_map):
        from xgboost import XGBClassifier
        from sklearn.ensemble import GradientBoostingClassifier

        X, y, Xs, ys = [], [], [], []
        current = {}   # symbol -> latest feature row + seq row
        for sym, bars in bars_map.items():
            close = np.array([b["close"] for b in bars], dtype=float)
            volume = np.array([b.get("volume", 0) for b in bars], dtype=float)
            if len(close) < 90:
                continue
            feats, logret = _series_features(close, volume)
            n = len(close)
            for i in range(60, n - FWD):
                if np.isnan(feats[i]).any():
                    continue
                fwd = close[i + FWD] / close[i] - 1
                # tercile-ish label thresholds
                lbl = 2 if fwd > 0.03 else (0 if fwd < -0.03 else 1)
                X.append(feats[i]); y.append(lbl)
            # direction sequence samples
            for i in range(SEQ, n - 1):
                Xs.append(logret[i - SEQ: i])
                ys.append(1 if close[i + 1] > close[i] else 0)
            # current prediction inputs (last valid)
            last = feats[-1]
            current[sym] = {"feat": None if np.isnan(last).any() else last,
                            "seq": logret[-SEQ:]}
        if len(X) < 200:
            logger.warning("insufficient ML data; skipping training")
            return {}

        X = np.array(X); y = np.array(y)
        Xs = np.array(Xs); ys = np.array(ys)
        # walk-forward: train on first 80% chronologically-ish (shuffle-free split)
        # Purged K-Fold cross-validation (Lopez de Prado method)
        ic_scores = []
        for train_idx, test_idx in purged_kfold_cv(X, y):
            self.clf = XGBClassifier(n_estimators=180, max_depth=4, learning_rate=0.06,
                                     subsample=0.85, colsample_bytree=0.8,
                                     eval_metric="mlogloss", num_class=3,
                                     objective="multi:softprob", n_jobs=2, verbosity=0)
            self.clf.fit(X[train_idx], y[train_idx])
            preds = self.clf.predict(X[test_idx])
            ic_scores.append(float((preds == y[test_idx]).mean()))
        cv_accuracy = float(np.mean(ic_scores)) if ic_scores else 0.0
        self.clf = XGBClassifier(n_estimators=180, max_depth=4, learning_rate=0.06,
                                 subsample=0.85, colsample_bytree=0.8, eval_metric="mlogloss",
                                 num_class=3, objective="multi:softprob", n_jobs=2, verbosity=0)
        self.clf.fit(X[:cut], y[:cut])
        try:
            acc = float((self.clf.predict(X[cut:]) == y[cut:]).mean())
        except Exception:
            acc = 0.0
        cut2 = int(len(Xs) * 0.85)
        self.dir_model = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.06)
        self.dir_model.fit(Xs[:cut2], ys[:cut2])
        self.trained = True
        logger.info(f"ML trained: clf_acc={acc:.3f} on {len(X)} samples, {len(Xs)} seq samples")

        preds = {}
        for sym, cur in current.items():
            if cur["feat"] is None:
                continue
            proba = self.clf.predict_proba(cur["feat"].reshape(1, -1))[0]  # [sell,hold,buy]
            buy_p = float(proba[2]); sell_p = float(proba[0])
            ml_score = round(50 + (buy_p - sell_p) * 50, 1)  # 0-100
            ml_signal = "BUY" if buy_p > 0.45 and buy_p >= sell_p else ("SELL" if sell_p > 0.45 else "HOLD")
            dprob = float(self.dir_model.predict_proba(cur["seq"].reshape(1, -1))[0][1]) * 100
            preds[sym] = {"ml_score": max(0, min(100, ml_score)),
                          "ml_signal": ml_signal,
                          "ml_buy_prob": round(buy_p * 100, 1),
                          "ml_sell_prob": round(sell_p * 100, 1),
                          "direction_prob": round(dprob, 1),
                          "model_acc": round(acc * 100, 1)}
        return preds


ml_engine = MLEngine()


def predict_bars(bars):
    """Predict ML score/signal/direction for an arbitrary stock's bars using the
    already-trained models. Returns {} if models not trained or data too short."""
    import numpy as _np
    if not ml_engine.trained or len(bars) < 90:
        return {}
    close = _np.array([b["close"] for b in bars], dtype=float)
    volume = _np.array([b.get("volume", 0) for b in bars], dtype=float)
    feats, logret = _series_features(close, volume)
    last = feats[-1]
    if _np.isnan(last).any():
        return {}
    try:
        proba = ml_engine.clf.predict_proba(last.reshape(1, -1))[0]
        buy_p = float(proba[2]); sell_p = float(proba[0])
        ml_score = round(50 + (buy_p - sell_p) * 50, 1)
        ml_signal = "BUY" if buy_p > 0.45 and buy_p >= sell_p else ("SELL" if sell_p > 0.45 else "HOLD")
        dprob = float(ml_engine.dir_model.predict_proba(logret[-SEQ:].reshape(1, -1))[0][1]) * 100
        return {"ml_score": max(0, min(100, ml_score)), "ml_signal": ml_signal,
                "ml_buy_prob": round(buy_p * 100, 1), "ml_sell_prob": round(sell_p * 100, 1),
                "direction_prob": round(dprob, 1)}
    except Exception:
        return {}
