"""Agent 2 reproducible statistical analysis for BEMM828 Chapter 5.

The script implements the locked workflow:
1. verify the analysis extract created from the raw XLSX;
2. run ordinal measurement diagnostics before any structural path estimates;
3. write a scoring lock;
4. estimate the pre-specified observed-score path model and bounded robustness.
"""

# Public repository release.
# This version preserves the analytical logic used in the dissertation.
# Changes from the archived executed version are limited to documentation
# and terminology clarification; no statistical model, scoring formula,
# hypothesis test, exclusion rule, or numerical procedure has been changed.

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Iterable

import numpy as np
from scipy import __version__ as scipy_version
from scipy import optimize, stats


ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "03_ANALYSIS" / "outputs" / "agent_2"
DATA_CSV = OUTDIR / "agent_2_locked_raw_fields.csv"
EXPECTED_RAW_SHA256 = "3a3bd2e7460ca30053b8f6e741a3dd83621774f988de68da72854021096d299e"
RANDOM_SEED = 82852026
BOOTSTRAP_RESAMPLES = 5000

ELIGIBILITY_FIELDS = ["ELIG_AGE", "ELIG_UK", "ELIG_DB12", "ELIG_ENG"]
PRIVACY_ITEMS = [
    "PC_CTRL1",
    "PC_CTRL2",
    "PC_AWA1",
    "PC_AWA2",
    "PC_COLL1",
    "PC_COLL2",
    "PC_COLL3",
    "PC_COLL4",
]
TRANSPARENCY_ITEMS = ["PT_D1", "PT_D2", "PT_C1", "PT_C2", "PT_A1", "PT_A2"]
TRUST_ITEMS = [
    "CT_COMP1",
    "CT_COMP2",
    "CT_COMP3",
    "CT_BEN1",
    "CT_BEN2",
    "CT_BEN3",
    "CT_INT1",
    "CT_INT2",
    "CT_INT3",
]
WTD_ITEMS = ["WTD1", "WTD2", "WTD3", "WTD4"]
FOCAL_ITEMS = PRIVACY_ITEMS + TRANSPARENCY_ITEMS + TRUST_ITEMS + WTD_ITEMS
DEMOGRAPHICS = ["DEM_AGE", "DEM_GENDER", "DEM_DBFREQ", "DEM_AIUSE"]

DIMENSIONS = {
    "Transparency_Disclosure": ["PT_D1", "PT_D2"],
    "Transparency_Clarity": ["PT_C1", "PT_C2"],
    "Transparency_Accuracy": ["PT_A1", "PT_A2"],
    "Privacy_Control": ["PC_CTRL1", "PC_CTRL2"],
    "Privacy_Awareness": ["PC_AWA1", "PC_AWA2"],
    "Privacy_Collection": ["PC_COLL1", "PC_COLL2", "PC_COLL3", "PC_COLL4"],
    "Trust_Competence": ["CT_COMP1", "CT_COMP2", "CT_COMP3"],
    "Trust_Benevolence": ["CT_BEN1", "CT_BEN2", "CT_BEN3"],
    "Trust_Integrity": ["CT_INT1", "CT_INT2", "CT_INT3"],
    "WTD": ["WTD1", "WTD2", "WTD3", "WTD4"],
}

STRUCTURAL_CONSTRUCTS = ["Transparency", "Privacy", "Trust", "WTD"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(name: str, payload: object) -> None:
    (OUTDIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(name: str, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with (OUTDIR / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_locked_csv() -> tuple[list[str], list[dict[str, str]]]:
    with DATA_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return reader.fieldnames or [], rows


def as_numeric_matrix(rows: list[dict[str, str]], cols: list[str]) -> np.ndarray:
    return np.array([[float(row[col]) for col in cols] for row in rows], dtype=float)


def mean(values: np.ndarray, cols: list[int]) -> np.ndarray:
    return values[:, cols].mean(axis=1)


def std_sample(x: np.ndarray) -> float:
    return float(np.std(x, ddof=1))


def skew_sample(x: np.ndarray) -> float:
    z = (x - x.mean()) / np.std(x, ddof=0)
    return float(np.mean(z**3))


def kurtosis_excess(x: np.ndarray) -> float:
    z = (x - x.mean()) / np.std(x, ddof=0)
    return float(np.mean(z**4) - 3.0)


def cronbach_alpha(x: np.ndarray) -> float:
    k = x.shape[1]
    if k < 2:
        return float("nan")
    item_var = x.var(axis=0, ddof=1).sum()
    total_var = x.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - item_var / total_var))


def corr_pair(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(x, y)[0, 1])


def corr_matrix(x: np.ndarray) -> np.ndarray:
    return np.corrcoef(x, rowvar=False)


def poly_thresholds(x: np.ndarray) -> np.ndarray:
    vals, counts = np.unique(x.astype(int), return_counts=True)
    cum = np.cumsum(counts)[:-1] / len(x)
    cum = np.clip(cum, 1e-5, 1 - 1e-5)
    return stats.norm.ppf(cum)


def rect_prob(lo_x: float, hi_x: float, lo_y: float, hi_y: float, rho: float) -> float:
    cov = [[1.0, rho], [rho, 1.0]]

    def cdf(a: float, b: float) -> float:
        if math.isinf(a) and a < 0:
            return 0.0
        if math.isinf(b) and b < 0:
            return 0.0
        if math.isinf(a) and a > 0 and math.isinf(b) and b > 0:
            return 1.0
        if math.isinf(a) and a > 0:
            return stats.norm.cdf(b)
        if math.isinf(b) and b > 0:
            return stats.norm.cdf(a)
        return float(stats.multivariate_normal.cdf([a, b], mean=[0, 0], cov=cov))

    p = cdf(hi_x, hi_y) - cdf(lo_x, hi_y) - cdf(hi_x, lo_y) + cdf(lo_x, lo_y)
    return max(p, 1e-12)


def polychoric_pair(x: np.ndarray, y: np.ndarray) -> float:
    tx = poly_thresholds(x)
    ty = poly_thresholds(y)
    bx = np.concatenate(([-np.inf], tx, [np.inf]))
    by = np.concatenate(([-np.inf], ty, [np.inf]))
    x_vals = sorted(np.unique(x.astype(int)))
    y_vals = sorted(np.unique(y.astype(int)))
    table = np.zeros((len(x_vals), len(y_vals)), dtype=float)
    x_index = {v: i for i, v in enumerate(x_vals)}
    y_index = {v: i for i, v in enumerate(y_vals)}
    for a, b in zip(x.astype(int), y.astype(int)):
        table[x_index[a], y_index[b]] += 1

    def neg_ll(rho: float) -> float:
        total = 0.0
        for i in range(table.shape[0]):
            for j in range(table.shape[1]):
                if table[i, j]:
                    total -= table[i, j] * math.log(rect_prob(bx[i], bx[i + 1], by[j], by[j + 1], rho))
        return total

    result = optimize.minimize_scalar(neg_ll, bounds=(-0.97, 0.97), method="bounded", options={"xatol": 1e-4})
    if not result.success:
        return corr_pair(x, y)
    return float(result.x)


def nearest_correlation(r: np.ndarray) -> np.ndarray:
    sym = (r + r.T) / 2
    vals, vecs = np.linalg.eigh(sym)
    vals = np.clip(vals, 1e-4, None)
    adjusted = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(adjusted))
    adjusted = adjusted / np.outer(d, d)
    np.fill_diagonal(adjusted, 1.0)
    return adjusted


def polychoric_matrix(x: np.ndarray, labels: list[str]) -> np.ndarray:
    cache_path = OUTDIR / "polychoric_item_correlation_matrix.csv"
    meta_path = OUTDIR / "polychoric_item_correlation_matrix.meta.json"
    data_hash = hashlib.sha256(x.astype(np.int16).tobytes()).hexdigest()
    if cache_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("data_hash") == data_hash and meta.get("labels") == labels:
            with cache_path.open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                arr = np.array([[float(v) for v in row[1:]] for row in reader], dtype=float)
            if header[1:] == labels:
                return arr

    p = x.shape[1]
    r = np.eye(p)
    for i in range(p):
        for j in range(i + 1, p):
            r[i, j] = r[j, i] = polychoric_pair(x[:, i], x[:, j])
    r = nearest_correlation(r)
    with cache_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["item"] + labels)
        for label, row in zip(labels, r):
            writer.writerow([label] + [f"{v:.10f}" for v in row])
    meta_path.write_text(json.dumps({"labels": labels, "data_hash": data_hash}, indent=2), encoding="utf-8")
    return r


@dataclass
class CfaModel:
    name: str
    item_labels: list[str]
    factor_names: list[str]
    item_factor: list[int]
    target_r: np.ndarray
    n: int

    @property
    def p(self) -> int:
        return len(self.item_labels)

    @property
    def q(self) -> int:
        return len(self.factor_names)

    def unpack(self, params: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        loadings = 0.15 + 0.84 / (1.0 + np.exp(-params[: self.p]))
        raw_corr = np.tanh(params[self.p :])
        phi = np.eye(self.q)
        idx = 0
        for i in range(self.q):
            for j in range(i + 1, self.q):
                phi[i, j] = phi[j, i] = raw_corr[idx]
                idx += 1
        return loadings, phi

    def implied(self, params: np.ndarray) -> np.ndarray:
        loadings, phi = self.unpack(params)
        sigma = np.eye(self.p)
        for i in range(self.p):
            fi = self.item_factor[i]
            for j in range(i + 1, self.p):
                fj = self.item_factor[j]
                value = loadings[i] * loadings[j] * (1.0 if fi == fj else phi[fi, fj])
                sigma[i, j] = sigma[j, i] = value
        return sigma

    def objective(self, params: np.ndarray) -> float:
        loadings, phi = self.unpack(params)
        min_eig = np.linalg.eigvalsh(phi).min()
        if min_eig <= 1e-4:
            return 1e5 + (1e-4 - min_eig) * 1e8
        sigma = self.implied(params)
        resid = self.target_r - sigma
        off = resid[np.triu_indices(self.p, 1)]
        return float(np.mean(off * off))


def initial_cfa_params(model: CfaModel, item_data: np.ndarray) -> np.ndarray:
    factor_scores = []
    loadings = []
    for item_idx, factor_idx in enumerate(model.item_factor):
        cols = [i for i, f in enumerate(model.item_factor) if f == factor_idx]
        score = item_data[:, cols].mean(axis=1)
        loadings.append(np.clip(abs(corr_pair(item_data[:, item_idx], score)), 0.25, 0.95))
    for factor_idx in range(model.q):
        cols = [i for i, f in enumerate(model.item_factor) if f == factor_idx]
        factor_scores.append(item_data[:, cols].mean(axis=1))
    phi_start = np.eye(model.q) if model.q == 1 else nearest_correlation(corr_matrix(np.column_stack(factor_scores)))
    load_raw = np.log((np.array(loadings) - 0.15) / (0.99 - np.array(loadings)))
    corr_raw = []
    for i in range(model.q):
        for j in range(i + 1, model.q):
            corr_raw.append(np.arctanh(np.clip(phi_start[i, j], -0.90, 0.90)))
    return np.concatenate([load_raw, np.array(corr_raw)])


def fit_cfa(
    name: str,
    item_labels: list[str],
    item_data: np.ndarray,
    target_r: np.ndarray,
    factor_map: dict[str, list[str]],
) -> dict[str, object]:
    factor_names = list(factor_map)
    item_factor = []
    for label in item_labels:
        item_factor.append(next(i for i, factor in enumerate(factor_names) if label in factor_map[factor]))
    model = CfaModel(name, item_labels, factor_names, item_factor, target_r, item_data.shape[0])
    start = initial_cfa_params(model, item_data)
    result = optimize.minimize(model.objective, start, method="L-BFGS-B", options={"maxiter": 2000, "ftol": 1e-12})
    params = result.x
    sigma = nearest_correlation(model.implied(params))
    loadings, phi = model.unpack(params)
    resid = target_r - sigma
    off = resid[np.triu_indices(model.p, 1)]
    srmr = float(np.sqrt(np.mean(off * off)))
    free_params = model.p + model.q * (model.q - 1) // 2
    df = model.p * (model.p - 1) // 2 - free_params
    fit = approximate_fit_indices(target_r, sigma, model.n, df)
    rows = []
    for label, loading, f_idx in zip(item_labels, loadings, item_factor):
        rows.append(
            {
                "model": name,
                "item": label,
                "factor": factor_names[f_idx],
                "standardized_loading": round(float(loading), 4),
                "indicator_reliability": round(float(loading * loading), 4),
            }
        )
    phi_rows = []
    for i, a in enumerate(factor_names):
        for j, b in enumerate(factor_names):
            if j > i:
                phi_rows.append({"factor_a": a, "factor_b": b, "correlation": round(float(phi[i, j]), 4)})
    return {
        "name": name,
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
        "estimator": "polychoric-correlation limited-information CFA; unweighted least-squares objective on off-diagonal polychoric correlation residuals",
        "n": model.n,
        "items": model.p,
        "factors": model.q,
        "free_parameters": free_params,
        "degrees_of_freedom": df,
        "srmr": srmr,
        "fit_indices": fit,
        "loadings": rows,
        "factor_correlations": phi_rows,
        "objective": float(result.fun),
    }


def fit_one_factor(item_labels: list[str], item_data: np.ndarray, target_r: np.ndarray) -> dict[str, object]:
    return fit_cfa("common_method_single_factor", item_labels, item_data, target_r, {"Single_Common_Factor": item_labels})


def approximate_fit_indices(r: np.ndarray, sigma: np.ndarray, n: int, df: int) -> dict[str, float | None]:
    p = r.shape[0]
    eps = 1e-5
    r_pd = nearest_correlation(r)
    sigma_pd = nearest_correlation(sigma)
    sign_r, logdet_r = np.linalg.slogdet(r_pd)
    sign_s, logdet_s = np.linalg.slogdet(sigma_pd)
    if sign_r <= 0 or sign_s <= 0:
        return {"chi_square_approx": None, "cfi_approx": None, "tli_approx": None, "rmsea_approx": None}
    inv_s = np.linalg.inv(sigma_pd)
    f_ml = logdet_s + np.trace(r_pd @ inv_s) - logdet_r - p
    chi = max((n - 1) * f_ml, 0.0)
    sigma0 = np.eye(p)
    sign_0, logdet_0 = np.linalg.slogdet(sigma0)
    inv_0 = np.linalg.inv(sigma0)
    f0 = logdet_0 + np.trace(r_pd @ inv_0) - logdet_r - p
    df0 = p * (p - 1) // 2
    chi0 = max((n - 1) * f0, eps)
    cfi = 1 - max(chi - df, 0) / max(chi0 - df0, eps)
    tli = (chi0 / df0 - chi / max(df, 1)) / max(chi0 / df0 - 1, eps) if df > 0 else None
    rmsea = math.sqrt(max((chi - df) / max(df * (n - 1), 1), 0.0)) if df > 0 else None
    return {
        "chi_square_approx": round(float(chi), 4),
        "df": int(df),
        "cfi_approx": round(float(cfi), 4),
        "tli_approx": round(float(tli), 4) if tli is not None else None,
        "rmsea_approx": round(float(rmsea), 4) if rmsea is not None else None,
    }


def composite_reliability_ave(loadings: list[float]) -> tuple[float, float]:
    lam = np.array(loadings, dtype=float)
    err = 1.0 - lam**2
    cr = (lam.sum() ** 2) / ((lam.sum() ** 2) + err.sum())
    ave = (lam**2).sum() / ((lam**2).sum() + err.sum())
    return float(cr), float(ave)


def htmt(data: dict[str, np.ndarray], items_a: list[str], items_b: list[str]) -> float:
    xa = np.column_stack([data[i] for i in items_a])
    xb = np.column_stack([data[i] for i in items_b])
    het = np.mean([abs(corr_pair(xa[:, i], xb[:, j])) for i in range(xa.shape[1]) for j in range(xb.shape[1])])
    mono_a = [abs(corr_pair(xa[:, i], xa[:, j])) for i in range(xa.shape[1]) for j in range(i + 1, xa.shape[1])]
    mono_b = [abs(corr_pair(xb[:, i], xb[:, j])) for i in range(xb.shape[1]) for j in range(i + 1, xb.shape[1])]
    return float(het / math.sqrt(np.mean(mono_a) * np.mean(mono_b)))


def ols(y: np.ndarray, x: np.ndarray, names: list[str]) -> dict[str, object]:
    n, k = x.shape
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    resid = y - x @ beta
    df = n - k
    s2 = float((resid @ resid) / df)
    cov = s2 * np.linalg.inv(x.T @ x)
    se = np.sqrt(np.diag(cov))
    tvals = beta / se
    pvals = 2 * stats.t.sf(np.abs(tvals), df)
    ci_low = beta - stats.t.ppf(0.975, df) * se
    ci_high = beta + stats.t.ppf(0.975, df) * se
    sst = float(((y - y.mean()) @ (y - y.mean())))
    r2 = 1 - float((resid @ resid) / sst)
    rows = []
    for i, name in enumerate(names):
        rows.append(
            {
                "term": name,
                "estimate": round(float(beta[i]), 6),
                "std_error": round(float(se[i]), 6),
                "t": round(float(tvals[i]), 4),
                "p": round(float(pvals[i]), 6),
                "ci95_low": round(float(ci_low[i]), 6),
                "ci95_high": round(float(ci_high[i]), 6),
            }
        )
    return {"n": n, "df_residual": df, "r_squared": round(r2, 6), "terms": rows, "beta": beta}


def design_matrix(columns: list[np.ndarray], names: list[str]) -> tuple[np.ndarray, list[str]]:
    return np.column_stack([np.ones(len(columns[0]))] + columns), ["Intercept"] + names


def standardised_ols(y: np.ndarray, predictors: list[np.ndarray], names: list[str]) -> dict[str, float]:
    yz = (y - y.mean()) / y.std(ddof=1)
    xz = [(x - x.mean()) / x.std(ddof=1) for x in predictors]
    x, term_names = design_matrix(xz, names)
    result = ols(yz, x, term_names)
    return {row["term"]: row["estimate"] for row in result["terms"] if row["term"] != "Intercept"}


def dummy_columns(values: list[str], prefix: str) -> tuple[list[np.ndarray], list[str]]:
    cats = sorted(set(values))
    baseline = "Prefer not to say" if "Prefer not to say" in cats else cats[0]
    cols = []
    names = []
    for cat in cats:
        if cat == baseline:
            continue
        cols.append(np.array([1.0 if v == cat else 0.0 for v in values]))
        names.append(f"{prefix}: {cat}")
    return cols, names


def bootstrap_indirect(
    trust: np.ndarray,
    wtd: np.ndarray,
    transparency: np.ndarray,
    privacy: np.ndarray,
    resamples: int,
    seed: int,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    n = len(trust)
    x_trust, names_trust = design_matrix([transparency, privacy], ["Transparency", "Privacy"])
    obs_trust = ols(trust, x_trust, names_trust)
    x_wtd, names_wtd = design_matrix([privacy, trust, transparency], ["Privacy", "Trust", "Transparency"])
    obs_wtd = ols(wtd, x_wtd, names_wtd)
    a_pt = obs_trust["beta"][1]
    a_pc = obs_trust["beta"][2]
    b_trust = obs_wtd["beta"][2]
    observed = {"H5": float(a_pt * b_trust), "H6": float(a_pc * b_trust)}
    draws = {"H5": [], "H6": []}
    for _ in range(resamples):
        idx = rng.integers(0, n, n)
        tr_b = trust[idx]
        wtd_b = wtd[idx]
        pt_b = transparency[idx]
        pc_b = privacy[idx]
        b_x_trust, b_names_trust = design_matrix([pt_b, pc_b], ["Transparency", "Privacy"])
        b_trust_result = ols(tr_b, b_x_trust, b_names_trust)
        b_x_wtd, b_names_wtd = design_matrix([pc_b, tr_b, pt_b], ["Privacy", "Trust", "Transparency"])
        b_wtd_result = ols(wtd_b, b_x_wtd, b_names_wtd)
        draws["H5"].append(float(b_trust_result["beta"][1] * b_wtd_result["beta"][2]))
        draws["H6"].append(float(b_trust_result["beta"][2] * b_wtd_result["beta"][2]))
    nd = NormalDist()
    rows = []
    for hyp in ["H5", "H6"]:
        arr = np.array(draws[hyp])
        prop = np.clip(np.mean(arr < observed[hyp]), 1 / (2 * resamples), 1 - 1 / (2 * resamples))
        z0 = nd.inv_cdf(float(prop))
        pct_low = 100 * nd.cdf(2 * z0 + nd.inv_cdf(0.025))
        pct_high = 100 * nd.cdf(2 * z0 + nd.inv_cdf(0.975))
        low, high = np.percentile(arr, [pct_low, pct_high])
        rows.append(
            {
                "hypothesis": hyp,
                "observed_indirect": round(observed[hyp], 6),
                "bootstrap_mean": round(float(arr.mean()), 6),
                "bootstrap_se": round(float(arr.std(ddof=1)), 6),
                "bias_correction_z0": round(float(z0), 4),
                "bc_ci95_low": round(float(low), 6),
                "bc_ci95_high": round(float(high), 6),
                "resamples": resamples,
                "seed": seed,
            }
        )
    return {"rows": rows, "draw_count": {k: len(v) for k, v in draws.items()}}


def counts(values: Iterable[str]) -> list[dict[str, object]]:
    vals = list(values)
    total = len(vals)
    return [
        {"category": k, "n": vals.count(k), "percent": round(100 * vals.count(k) / total, 2)}
        for k in sorted(set(vals))
    ]


def main() -> None:
    start = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    headers, rows = read_locked_csv()
    if len(rows) != 300:
        raise SystemExit(f"Expected 300 retained cases; found {len(rows)}")
    item_matrix = as_numeric_matrix(rows, FOCAL_ITEMS)
    item_data = {name: item_matrix[:, i] for i, name in enumerate(FOCAL_ITEMS)}
    col_index = {name: FOCAL_ITEMS.index(name) for name in FOCAL_ITEMS}
    eligible = all(all(row[field] == "Yes" for field in ELIGIBILITY_FIELDS) for row in rows)
    focal_complete = bool(np.isfinite(item_matrix).all())
    if not eligible or not focal_complete:
        raise SystemExit("Primary sample is not fully eligible and focal-complete.")

    straightline_masks = {
        "privacy_block_all_8_same": np.ptp(as_numeric_matrix(rows, PRIVACY_ITEMS), axis=1) == 0,
        "transparency_block_all_6_same": np.ptp(as_numeric_matrix(rows, TRANSPARENCY_ITEMS), axis=1) == 0,
        "trust_block_all_9_same": np.ptp(as_numeric_matrix(rows, TRUST_ITEMS), axis=1) == 0,
        "wtd_block_all_4_same": np.ptp(as_numeric_matrix(rows, WTD_ITEMS), axis=1) == 0,
        "all_27_focal_items_same": np.ptp(item_matrix, axis=1) == 0,
    }
    any_straightline = (
        straightline_masks["privacy_block_all_8_same"]
        | straightline_masks["transparency_block_all_6_same"]
        | straightline_masks["trust_block_all_9_same"]
        | straightline_masks["wtd_block_all_4_same"]
    )

    dimension_scores = {
        name: mean(item_matrix, [col_index[c] for c in cols]) for name, cols in DIMENSIONS.items()
    }
    construct_scores = {
        "Transparency": np.column_stack(
            [
                dimension_scores["Transparency_Disclosure"],
                dimension_scores["Transparency_Clarity"],
                dimension_scores["Transparency_Accuracy"],
            ]
        ).mean(axis=1),
        "Privacy": np.column_stack(
            [
                dimension_scores["Privacy_Control"],
                dimension_scores["Privacy_Awareness"],
                dimension_scores["Privacy_Collection"],
            ]
        ).mean(axis=1),
        "Trust": np.column_stack(
            [
                dimension_scores["Trust_Competence"],
                dimension_scores["Trust_Benevolence"],
                dimension_scores["Trust_Integrity"],
            ]
        ).mean(axis=1),
        "WTD": dimension_scores["WTD"],
    }
    scores_rows = []
    for i, row in enumerate(rows):
        output = {"Respondent_ID": row["Respondent_ID"]}
        output.update({name: round(float(values[i]), 8) for name, values in dimension_scores.items()})
        output.update({name: round(float(values[i]), 8) for name, values in construct_scores.items()})
        output["any_construct_block_straightline"] = bool(any_straightline[i])
        scores_rows.append(output)
    write_csv("agent_2_locked_scores.csv", scores_rows)

    poly_r = polychoric_matrix(item_matrix, FOCAL_ITEMS)
    measurement_model = fit_cfa("confirmatory_ten_dimension_measurement_model", FOCAL_ITEMS, item_matrix, poly_r, DIMENSIONS)
    single_factor_model = fit_one_factor(FOCAL_ITEMS, item_matrix, poly_r)
    write_json("measurement_cfa_results.json", measurement_model)
    write_json("common_method_single_factor_cfa.json", single_factor_model)
    write_csv("measurement_standardized_loadings.csv", measurement_model["loadings"])
    write_csv("measurement_factor_correlations.csv", measurement_model["factor_correlations"])

    loading_by_item = {row["item"]: row["standardized_loading"] for row in measurement_model["loadings"]}
    reliability_rows = []
    for name, cols in DIMENSIONS.items():
        x = np.column_stack([item_data[c] for c in cols])
        cr, ave = composite_reliability_ave([loading_by_item[c] for c in cols])
        reliability_rows.append(
            {
                "unit": name,
                "items": len(cols),
                "alpha_raw": round(cronbach_alpha(x), 4),
                "composite_reliability_from_cfa": round(cr, 4),
                "ave_from_cfa": round(ave, 4),
                "note": "Two-item dimensions are diagnostics within the source architecture, not independently validated standalone scales."
                if len(cols) == 2
                else "",
            }
        )
    for construct, cols in {
        "Transparency_project_composite": TRANSPARENCY_ITEMS,
        "Privacy_project_composite": PRIVACY_ITEMS,
        "Trust_dimension_composite": TRUST_ITEMS,
        "WTD_construct": WTD_ITEMS,
    }.items():
        x = np.column_stack([item_data[c] for c in cols])
        cr, ave = composite_reliability_ave([loading_by_item[c] for c in cols])
        reliability_rows.append(
            {
                "unit": construct,
                "items": len(cols),
                "alpha_raw": round(cronbach_alpha(x), 4),
                "composite_reliability_from_cfa": round(cr, 4),
                "ave_from_cfa": round(ave, 4),
                "note": "Project-level reliability summary from locked item set; scoring rationale is in SCORING_LOCK.md.",
            }
        )
    write_csv("reliability_validity_summary.csv", reliability_rows)

    construct_matrix = np.column_stack([construct_scores[c] for c in STRUCTURAL_CONSTRUCTS])
    construct_corr = corr_matrix(construct_matrix)
    corr_rows = []
    for i, a in enumerate(STRUCTURAL_CONSTRUCTS):
        for j, b in enumerate(STRUCTURAL_CONSTRUCTS):
            corr_rows.append({"row": a, "column": b, "correlation": round(float(construct_corr[i, j]), 4)})
    write_csv("construct_correlations.csv", corr_rows)

    ave_map = {row["unit"]: row["ave_from_cfa"] for row in reliability_rows}
    ave_construct = {
        "Transparency": ave_map["Transparency_project_composite"],
        "Privacy": ave_map["Privacy_project_composite"],
        "Trust": ave_map["Trust_dimension_composite"],
        "WTD": ave_map["WTD_construct"],
    }
    fornell_rows = []
    for i, a in enumerate(STRUCTURAL_CONSTRUCTS):
        for j, b in enumerate(STRUCTURAL_CONSTRUCTS):
            value = math.sqrt(ave_construct[a]) if i == j else construct_corr[i, j]
            fornell_rows.append({"row": a, "column": b, "value": round(float(value), 4)})
    write_csv("fornell_larcker_matrix.csv", fornell_rows)

    htmt_pairs = [
        ("Transparency", TRANSPARENCY_ITEMS, "Privacy", PRIVACY_ITEMS),
        ("Trust", TRUST_ITEMS, "WTD", WTD_ITEMS),
        ("Trust", TRUST_ITEMS, "Privacy", PRIVACY_ITEMS),
        ("Transparency", TRANSPARENCY_ITEMS, "Trust", TRUST_ITEMS),
        ("Transparency", TRANSPARENCY_ITEMS, "WTD", WTD_ITEMS),
        ("Privacy", PRIVACY_ITEMS, "WTD", WTD_ITEMS),
    ]
    htmt_rows = [
        {"construct_a": a, "construct_b": b, "htmt": round(htmt(item_data, items_a, items_b), 4)}
        for a, items_a, b, items_b in htmt_pairs
    ]
    write_csv("htmt_results.csv", htmt_rows)

    scoring_lock = f"""# Agent 2 SCORING LOCK

This file was written by executed code before structural path results were
estimated. The lock is based on the final questionnaire architecture, Chapter 3
requirements, and the confirmatory ordinal measurement assessment in
`measurement_cfa_results.json`.

## Final construct representation

- Transparency: six 5-point items retaining Disclosure, Clarity and Accuracy
  mappings. The three two-item dimensions are retained as architecture and
  diagnostics, not as independently validated standalone scales.
- Privacy concerns: IUIPC-8 retaining the three source dimensions of Control,
  Awareness and Collection. The project score is an equally weighted composite
  across these three dimension scores. Control and Awareness are not standalone
  two-item scales.
- Trust: three correlated belief dimensions: Competence, Benevolence and
  Integrity. The structural mediator is a unit-weighted dimensional composite,
  not an asserted higher-order latent trust factor.
- WTD: four 5-point stated-intention items.

## Exact score formula

- Transparency_Disclosure = mean(PT_D1, PT_D2)
- Transparency_Clarity = mean(PT_C1, PT_C2)
- Transparency_Accuracy = mean(PT_A1, PT_A2)
- Transparency = mean(Transparency_Disclosure, Transparency_Clarity,
  Transparency_Accuracy), equivalent to the mean of all six transparency items
  because each dimension has two items.
- Privacy_Control = mean(PC_CTRL1, PC_CTRL2)
- Privacy_Awareness = mean(PC_AWA1, PC_AWA2)
- Privacy_Collection = mean(PC_COLL1, PC_COLL2, PC_COLL3, PC_COLL4)
- Privacy = mean(Privacy_Control, Privacy_Awareness, Privacy_Collection). This
  equally weights the three IUIPC dimensions and avoids overweighting Collection
  merely because it has four indicators.
- Trust_Competence = mean(CT_COMP1, CT_COMP2, CT_COMP3)
- Trust_Benevolence = mean(CT_BEN1, CT_BEN2, CT_BEN3)
- Trust_Integrity = mean(CT_INT1, CT_INT2, CT_INT3)
- Trust = mean(Trust_Competence, Trust_Benevolence, Trust_Integrity), which is
  equivalent to the nine-item mean because the three trust dimensions have equal
  item counts.
- WTD = mean(WTD1, WTD2, WTD3, WTD4)

## Treatment decisions

All 300 eligible and focal-complete retained cases are included in the primary
analysis. Straight-line flags are retained as diagnostic-only sensitivity
indicators. No reverse coding, item deletion, timing exclusion, retrospective
power analysis, or workbook-derived composite score is used.

## Alternatives considered and rejected

- Raw eight-item Privacy mean: rejected because it would give Collection twice
  the weight of Control or Awareness and would conflict with the retained
  three-dimension IUIPC scoring architecture.
- Separate structural paths for trust dimensions: rejected because Chapter 3
  locks customer trust as the single statistical mediator and authorises no new
  hypotheses or subgroup/model search.
- Higher-order latent trust score: rejected because Chapter 3 says trust
  retains three correlated dimensions and requires explicit justification before
  a higher-order treatment. The observed mediator is therefore a transparent
  unit-weighted dimension composite.
- Item deletion to improve fit or significance: rejected by the analysis lock.
"""
    (OUTDIR / "SCORING_LOCK.md").write_text(scoring_lock, encoding="utf-8")

    descriptive_rows = []
    for name in STRUCTURAL_CONSTRUCTS:
        x = construct_scores[name]
        descriptive_rows.append(
            {
                "construct": name,
                "n": len(x),
                "mean": round(float(x.mean()), 4),
                "sd": round(std_sample(x), 4),
                "min": round(float(x.min()), 4),
                "max": round(float(x.max()), 4),
                "skew": round(skew_sample(x), 4),
                "excess_kurtosis": round(kurtosis_excess(x), 4),
            }
        )
    write_csv("construct_descriptives.csv", descriptive_rows)

    demographic_payload = {
        col: counts([row[col] for row in rows])
        for col in DEMOGRAPHICS
    }
    write_json("sample_profile_demographics.json", demographic_payload)
    sample_rows = []
    for col, values in demographic_payload.items():
        for row in values:
            out = {"variable": col}
            out.update(row)
            sample_rows.append(out)
    write_csv("sample_profile_demographics.csv", sample_rows)

    transparency = construct_scores["Transparency"]
    privacy = construct_scores["Privacy"]
    trust = construct_scores["Trust"]
    wtd = construct_scores["WTD"]

    x_trust, names_trust = design_matrix([transparency, privacy], ["Transparency", "Privacy"])
    trust_model = ols(trust, x_trust, names_trust)
    x_wtd, names_wtd = design_matrix([privacy, trust, transparency], ["Privacy", "Trust", "Transparency"])
    wtd_model = ols(wtd, x_wtd, names_wtd)
    std_trust = standardised_ols(trust, [transparency, privacy], ["Transparency", "Privacy"])
    std_wtd = standardised_ols(wtd, [privacy, trust, transparency], ["Privacy", "Trust", "Transparency"])
    for row in trust_model["terms"]:
        row["standardized_estimate"] = std_trust.get(row["term"], "")
        row["equation"] = "Trust"
    for row in wtd_model["terms"]:
        row["standardized_estimate"] = std_wtd.get(row["term"], "")
        row["equation"] = "WTD"
    direct_rows = [
        {
            "path": "H2 Transparency -> Trust",
            **next(r for r in trust_model["terms"] if r["term"] == "Transparency"),
        },
        {
            "path": "H3 Privacy -> Trust",
            **next(r for r in trust_model["terms"] if r["term"] == "Privacy"),
        },
        {
            "path": "H1 Privacy -> WTD",
            **next(r for r in wtd_model["terms"] if r["term"] == "Privacy"),
        },
        {
            "path": "H4 Trust -> WTD",
            **next(r for r in wtd_model["terms"] if r["term"] == "Trust"),
        },
        {
            "path": "P5 Transparency -> WTD (exploratory)",
            **next(r for r in wtd_model["terms"] if r["term"] == "Transparency"),
        },
    ]
    write_csv("structural_direct_paths.csv", direct_rows)
    r2_rows = [
        {"endogenous": "Trust", "r_squared": trust_model["r_squared"], "n": trust_model["n"]},
        {"endogenous": "WTD", "r_squared": wtd_model["r_squared"], "n": wtd_model["n"]},
    ]
    write_csv("structural_r_squared.csv", r2_rows)
    bootstrap = bootstrap_indirect(trust, wtd, transparency, privacy, BOOTSTRAP_RESAMPLES, RANDOM_SEED)
    write_csv("bootstrap_indirect_effects.csv", bootstrap["rows"])

    hypotheses = []
    direct_map = {row["path"].split(" ")[0]: row for row in direct_rows}
    expected = {
        "H1": "negative",
        "H2": "positive",
        "H3": "negative",
        "H4": "positive",
    }
    for hyp in ["H1", "H2", "H3", "H4"]:
        row = direct_map[hyp]
        sign_ok = (row["estimate"] < 0) if expected[hyp] == "negative" else (row["estimate"] > 0)
        supported = sign_ok and float(row["p"]) < 0.05
        hypotheses.append(
            {
                "hypothesis": hyp,
                "expected_direction": expected[hyp],
                "observed_estimate": row["estimate"],
                "p": row["p"],
                "evaluation": "Supported" if supported else "Not supported",
            }
        )
    for row, expected_direction in zip(bootstrap["rows"], ["positive", "negative"]):
        sign_ok = (row["observed_indirect"] > 0) if expected_direction == "positive" else (row["observed_indirect"] < 0)
        ci_excludes_zero = row["bc_ci95_low"] > 0 or row["bc_ci95_high"] < 0
        hypotheses.append(
            {
                "hypothesis": row["hypothesis"],
                "expected_direction": expected_direction,
                "observed_estimate": row["observed_indirect"],
                "p": "bootstrap CI",
                "evaluation": "Supported" if sign_ok and ci_excludes_zero else "Not supported",
            }
        )
    hypotheses.append(
        {
            "hypothesis": "P5 exploratory",
            "expected_direction": "none specified",
            "observed_estimate": direct_map["P5"]["estimate"],
            "p": direct_map["P5"]["p"],
            "evaluation": "Exploratory path reported, not a hypothesis",
        }
    )
    write_csv("hypothesis_evaluation.csv", hypotheses)

    age_cols, age_names = dummy_columns([row["DEM_AGE"] for row in rows], "Age")
    ai_cols, ai_names = dummy_columns([row["DEM_AIUSE"] for row in rows], "Prior AI/bank chatbot use")
    cov_cols = age_cols + ai_cols
    cov_names = age_names + ai_names
    r_x_trust, r_names_trust = design_matrix([transparency, privacy] + cov_cols, ["Transparency", "Privacy"] + cov_names)
    robustness_trust = ols(trust, r_x_trust, r_names_trust)
    r_x_wtd, r_names_wtd = design_matrix([privacy, trust, transparency] + cov_cols, ["Privacy", "Trust", "Transparency"] + cov_names)
    robustness_wtd = ols(wtd, r_x_wtd, r_names_wtd)
    robustness_rows = []
    for model_name, result in [("Trust_with_age_ai_covariates", robustness_trust), ("WTD_with_age_ai_covariates", robustness_wtd)]:
        for row in result["terms"]:
            if row["term"] in ["Transparency", "Privacy", "Trust"]:
                out = {"model": model_name, "r_squared": result["r_squared"]}
                out.update(row)
                robustness_rows.append(out)
    write_csv("robustness_age_ai_covariates.csv", robustness_rows)

    keep = ~any_straightline
    sens_transparency = transparency[keep]
    sens_privacy = privacy[keep]
    sens_trust = trust[keep]
    sens_wtd = wtd[keep]
    s_x_trust, s_names_trust = design_matrix([sens_transparency, sens_privacy], ["Transparency", "Privacy"])
    sens_trust_model = ols(sens_trust, s_x_trust, s_names_trust)
    s_x_wtd, s_names_wtd = design_matrix([sens_privacy, sens_trust, sens_transparency], ["Privacy", "Trust", "Transparency"])
    sens_wtd_model = ols(sens_wtd, s_x_wtd, s_names_wtd)
    sensitivity_rows = []
    for model_name, result in [("Trust_excluding_block_invariant", sens_trust_model), ("WTD_excluding_block_invariant", sens_wtd_model)]:
        for row in result["terms"]:
            if row["term"] in ["Transparency", "Privacy", "Trust"]:
                out = {"model": model_name, "n": result["n"], "r_squared": result["r_squared"]}
                out.update(row)
                sensitivity_rows.append(out)
    sensitivity_bootstrap = bootstrap_indirect(
        sens_trust,
        sens_wtd,
        sens_transparency,
        sens_privacy,
        BOOTSTRAP_RESAMPLES,
        RANDOM_SEED + 1,
    )
    write_csv("sensitivity_excluding_block_invariant.csv", sensitivity_rows)
    write_csv("sensitivity_excluding_block_invariant_bootstrap.csv", sensitivity_bootstrap["rows"])

    diagnostics = {
        "primary_n": len(rows),
        "eligible_all_yes": eligible,
        "focal_complete": focal_complete,
        "straightline_counts": {name: int(mask.sum()) for name, mask in straightline_masks.items()},
        "any_construct_block_straightline": int(any_straightline.sum()),
        "sensitivity_n_excluding_any_construct_block_straightline": int(keep.sum()),
        "completion_time_screening": "Not operable; no timing, duration, timestamp or progress fields are available in the raw export.",
        "antecedent_covariance": {
            "Transparency_with_Privacy_correlation": round(corr_pair(transparency, privacy), 4)
        },
    }
    write_json("sample_and_quality_diagnostics.json", diagnostics)

    session_info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "scipy_version": scipy_version,
        "random_seed": RANDOM_SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "raw_workbook_sha256_expected": EXPECTED_RAW_SHA256,
        "locked_extract_sha256": sha256(DATA_CSV),
        "estimator_measurement": measurement_model["estimator"],
        "structural_estimator": "ordinary least squares path analysis on locked observed composite scores",
        "elapsed_seconds": round(time.time() - start, 2),
    }
    write_json("software_session_info.json", session_info)
    (OUTDIR / "software_session_info.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in session_info.items()),
        encoding="utf-8",
    )

    manifest = {
        "code": [
            "03_ANALYSIS/code/01_data_audit.py",
            "03_ANALYSIS/code/02_prepare_inputs.py",
            "03_ANALYSIS/code/03_statistical_analysis.py",
        ],
        "outputs": sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in OUTDIR.glob("*")),
        "scoring_lock_written_before_structural_estimation": True,
        "no_post_hoc_item_or_case_deletion": True,
    }
    write_json("agent_2_result_manifest.json", manifest)
    print(json.dumps({"status": "PASS", "output_dir": str(OUTDIR), "elapsed_seconds": session_info["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
