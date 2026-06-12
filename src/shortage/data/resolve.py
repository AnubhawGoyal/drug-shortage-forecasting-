"""Week-2 entity resolution: shortage <-> Orange Book <-> NDC directory.

Builds the ingredient-level spine that everything downstream joins on.

Outputs (data/interim/):
    shortage_events.parquet   one row per shortage record, normalized ingredient
    orange_book_ing.parquet   Orange Book exploded to ingredient level
    ndc_ingredients.parquet   NDC directory exploded to ingredient level
    ingredient_spine.parquet  master ingredient table with match flags
    coverage.json             match-rate statistics for the coverage report
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_RAW

# Salt/ester suffixes stripped for the *loose* ingredient key (kept for exact key)
SALT_WORDS = (
    "HYDROCHLORIDE|HCL|SODIUM|POTASSIUM|CALCIUM|MAGNESIUM|SULFATE|SULPHATE|"
    "PHOSPHATE|DIPHOSPHATE|ACETATE|TARTRATE|BITARTRATE|MALEATE|MESYLATE|"
    "BESYLATE|TOSYLATE|CITRATE|FUMARATE|SUCCINATE|LACTATE|GLUCONATE|"
    "BROMIDE|CHLORIDE|IODIDE|NITRATE|CARBONATE|BICARBONATE|OXALATE|"
    "MONOHYDRATE|DIHYDRATE|TRIHYDRATE|ANHYDROUS|HEMIHYDRATE|SACCHARATE|"
    "ASPARTATE|PROPIONATE|VALERATE|DIPROPIONATE|PALMITATE|ENANTHATE|"
    "DECANOATE|UNDECANOATE|CYPIONATE|BENZOATE|SALICYLATE|STEARATE|EDETATE|"
    "DISODIUM|DIPOTASSIUM|TROMETHAMINE|MEGLUMINE|XINAFOATE|FUROATE"
)
_SALT_RE = re.compile(rf"\b(?:{SALT_WORDS})\b")

# Dosage-form / packaging words that FDA appends to generic_name
FORM_WORDS = (
    "TABLET|TABLETS|CAPSULE|CAPSULES|INJECTION|INJECTABLE|KIT|OINTMENT|CREAM|"
    "GEL|LOTION|SOLUTION|SUSPENSION|SYRUP|ELIXIR|POWDER|GRANULES|PATCH|FILM|"
    "OPHTHALMIC|TOPICAL|ORAL|NASAL|RECTAL|VAGINAL|OTIC|INHALATION|AEROSOL|"
    "SPRAY|SUPPOSITORY|SUPPOSITORIES|LOZENGE|EMULSION|CONCENTRATE|"
    "FOR|EXTENDED|DELAYED|RELEASE|CHEWABLE|DISPERSIBLE|SUBLINGUAL|PREFILLED|SYRINGE"
)
_FORM_RE = re.compile(rf"\b(?:{FORM_WORDS})\b")

# Biologics are not in the Orange Book (they live in the Purple Book) — flag, don't force-match
_BIO_RE = re.compile(
    r"(MAB\b|CEPT\b|PLASE\b|INSULIN|VACCINE|IMMUNE GLOBULIN|FACTOR [IVX]+|"
    r"PEGFILGRASTIM|FILGRASTIM|EPOETIN|SOMATROPIN|GLUCAGON\b|TOXIN\b)"
)
_NONWORD = re.compile(r"[^A-Z0-9 ]")
_WS = re.compile(r"\s+")

# Coarse dosage-form buckets (injectables are the analytically critical class)
FORM_MAP = [
    ("INJECT|PARENTER|IV |INTRAVEN|SYRINGE|VIAL|INFUS", "INJECTABLE"),
    ("TABLET|CAPLET", "TABLET"),
    ("CAPSULE", "CAPSULE"),
    ("SOLUTION|SUSPENSION|SYRUP|ELIXIR|LIQUID|DROPS", "LIQUID"),
    ("CREAM|OINTMENT|GEL|LOTION|TOPICAL|PATCH|FILM", "TOPICAL"),
    ("AEROSOL|INHAL|SPRAY|NEBUL", "INHALATION"),
    ("SUPPOSITOR", "SUPPOSITORY"),
    ("POWDER|GRANULE", "POWDER"),
]


def norm_exact(s: pd.Series) -> pd.Series:
    """Uppercase, strip punctuation, drop dosage-form words — exact ingredient key."""
    out = s.fillna("").astype(str).str.upper()
    out = out.str.replace(_NONWORD, " ", regex=True)
    out = out.str.replace(_FORM_RE, " ", regex=True)
    return out.str.replace(_WS, " ", regex=True).str.strip()


def norm_loose(s: pd.Series) -> pd.Series:
    """Exact key with salt/hydrate words removed — loose ingredient key."""
    out = norm_exact(s).str.replace(_SALT_RE, " ", regex=True)
    return out.str.replace(_WS, " ", regex=True).str.strip()


def map_form(s: pd.Series) -> pd.Series:
    up = s.fillna("").astype(str).str.upper()
    out = pd.Series("OTHER", index=s.index)
    for pat, label in FORM_MAP:
        hit = up.str.contains(pat, regex=True) & (out == "OTHER")
        out[hit] = label
    out[up.str.strip() == ""] = "UNKNOWN"
    return out


def _first(x):
    """First element of list/array-ish values, else the value itself."""
    if isinstance(x, (list, np.ndarray)):
        return x[0] if len(x) else None
    return x


def split_components(raw: pd.Series) -> pd.Series:
    """Split combination-product strings into component lists (on , ; / AND +)."""
    up = raw.fillna("").astype(str).str.upper()
    parts = up.str.split(r"\s*(?:[,;/+]|\bAND\b|\bWITH\b)\s*", regex=True)
    def clean(lst):
        out = []
        for x in lst:
            x = _NONWORD.sub(" ", x)
            x = _FORM_RE.sub(" ", x)
            x = _SALT_RE.sub(" ", x)
            x = _WS.sub(" ", x).strip()
            if x:
                out.append(x)
        return out
    return parts.map(clean)


# --------------------------------------------------------------------- builders
def build_shortage_events() -> pd.DataFrame:
    s = pd.read_parquet(DATA_RAW / "fda_shortages" / "data.parquet")
    sub = s["openfda.substance_name"].map(_first)
    ing_raw = sub.fillna(s["generic_name"])
    df = pd.DataFrame(
        {
            "ingredient_src": ing_raw,
            "ing_exact": norm_exact(ing_raw),
            "ing_loose": norm_loose(ing_raw),
            "ing_from": np.where(sub.notna(), "openfda_substance", "generic_name"),
            "components": split_components(ing_raw),
            "is_biologic": ing_raw.fillna("").astype(str).str.upper().str.contains(_BIO_RE),
            "generic_name": s["generic_name"],
            "company_name": s["company_name"],
            "dosage_form_raw": s["dosage_form"],
            "form": map_form(s["dosage_form"]),
            "status": s["status"],
            "shortage_reason": s["shortage_reason"],
            "therapeutic_category": s["therapeutic_category"].map(_first),
            "initial_posting_date": pd.to_datetime(s["initial_posting_date"], errors="coerce"),
            "update_date": pd.to_datetime(s["update_date"], errors="coerce"),
            "change_date": pd.to_datetime(s["change_date"], errors="coerce"),
            "package_ndc": s["package_ndc"],
            "product_ndc": s["openfda.product_ndc"].map(_first),
        }
    )
    df = df[df.ing_exact != ""].reset_index(drop=True)
    return df


def build_orange_book() -> pd.DataFrame:
    ob = pd.read_parquet(DATA_RAW / "orange_book" / "products.parquet")
    ob = ob.assign(ingredient=ob["Ingredient"].str.split("; ")).explode("ingredient")
    dfr = ob["DF;Route"].str.split(";", n=1, expand=True)
    df = pd.DataFrame(
        {
            "ing_exact": norm_exact(ob["ingredient"]),
            "ing_loose": norm_loose(ob["ingredient"]),
            "trade_name": ob["Trade_Name"],
            "applicant": ob["Applicant_Full_Name"],
            "df_raw": dfr[0],
            "route_raw": dfr[1],
            "form": map_form(ob["DF;Route"]),
            "appl_type": ob["Appl_Type"],  # N = NDA (brand), A = ANDA (generic)
            "appl_no": ob["Appl_No"],
            "te_code": ob["TE_Code"],
            "approval_date": pd.to_datetime(ob["Approval_Date"], errors="coerce", format="mixed"),
            "rx_otc_discn": ob["Type"],
        }
    )
    return df[df.ing_exact != ""].reset_index(drop=True)


def build_ndc_ingredients() -> pd.DataFrame:
    n = pd.read_parquet(DATA_RAW / "ndc_directory" / "part-0000.parquet")
    n = n.explode("active_ingredients")
    name = n["active_ingredients"].map(lambda d: d.get("name") if isinstance(d, dict) else None)
    df = pd.DataFrame(
        {
            "product_ndc": n["product_ndc"],
            "ing_exact": norm_exact(name),
            "ing_loose": norm_loose(name),
            "generic_name": n["generic_name"],
            "brand_name": n["brand_name"],
            "labeler": n["labeler_name"],
            "form": map_form(n["dosage_form"]),
            "route": n["route"].map(_first),
            "marketing_category": n["marketing_category"],
            "marketing_start": pd.to_datetime(n["marketing_start_date"], errors="coerce"),
            "application_number": n["application_number"],
            "dea_schedule": n["dea_schedule"],
        }
    )
    return df[df.ing_exact != ""].reset_index(drop=True)


def build_spine(
    ev: pd.DataFrame, ob: pd.DataFrame, ndc: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Ingredient spine = union of shortage ingredients, with OB/NDC match flags."""
    ob_exact, ob_loose = set(ob.ing_exact), set(ob.ing_loose)
    ndc_exact, ndc_loose = set(ndc.ing_exact), set(ndc.ing_loose)

    spine = (
        ev.groupby(["ing_exact", "ing_loose"])
        .agg(
            n_records=("ing_exact", "size"),
            n_companies=("company_name", "nunique"),
            first_posted=("initial_posting_date", "min"),
            last_posted=("initial_posting_date", "max"),
            any_current=("status", lambda x: bool((x == "Current").any())),
            forms=("form", lambda x: sorted(set(x))),
            ing_from=("ing_from", "first"),
            components=("components", "first"),
            is_biologic=("is_biologic", "any"),
        )
        .reset_index()
    )

    def comp_ok(comps, pool):
        return bool(comps) and all(c in pool for c in comps)

    spine["ob_match"] = np.select(
        [
            spine.ing_exact.isin(ob_exact),
            spine.ing_loose.isin(ob_loose),
            spine.components.map(lambda c: comp_ok(c, ob_loose)),
        ],
        ["exact", "loose", "component"], default="none",
    )
    spine["ndc_match"] = np.select(
        [
            spine.ing_exact.isin(ndc_exact),
            spine.ing_loose.isin(ndc_loose),
            spine.components.map(lambda c: comp_ok(c, ndc_loose)),
        ],
        ["exact", "loose", "component"], default="none",
    )

    def rates(col):
        c = spine.groupby(col)["n_records"].agg(["count", "sum"])
        return {
            k: {"ingredients": int(v["count"]), "records": int(v["sum"])}
            for k, v in c.iterrows()
        }

    cov = {
        "n_shortage_records": int(ev.shape[0]),
        "n_shortage_ingredients": int(spine.shape[0]),
        "ingredient_source": ev.ing_from.value_counts().to_dict(),
        "orange_book_match": rates("ob_match"),
        "ndc_match": rates("ndc_match"),
        "both_matched_ingredients": int(((spine.ob_match != "none") & (spine.ndc_match != "none")).sum()),
        "unmatched_ob_biologics": int(((spine.ob_match == "none") & spine.is_biologic).sum()),
        "ob_match_excl_biologics": {
            k: int(v) for k, v in spine.loc[~spine.is_biologic, "ob_match"].value_counts().items()
        },
        "unmatched_ob_examples": spine.loc[spine.ob_match == "none", "ing_exact"].head(15).tolist(),
        "unmatched_ndc_examples": spine.loc[spine.ndc_match == "none", "ing_exact"].head(15).tolist(),
    }
    return spine, cov


def main() -> None:
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    ev = build_shortage_events()
    ob = build_orange_book()
    ndc = build_ndc_ingredients()
    spine, cov = build_spine(ev, ob, ndc)

    ev.to_parquet(DATA_INTERIM / "shortage_events.parquet", index=False)
    ob.to_parquet(DATA_INTERIM / "orange_book_ing.parquet", index=False)
    ndc.to_parquet(DATA_INTERIM / "ndc_ingredients.parquet", index=False)
    spine.to_parquet(DATA_INTERIM / "ingredient_spine.parquet", index=False)
    (DATA_INTERIM / "coverage.json").write_text(json.dumps(cov, indent=2, default=str))

    print(f"shortage_events  {ev.shape}")
    print(f"orange_book_ing  {ob.shape}")
    print(f"ndc_ingredients  {ndc.shape}")
    print(f"ingredient_spine {spine.shape}")
    print(json.dumps({k: v for k, v in cov.items() if "examples" not in k}, indent=2, default=str))


if __name__ == "__main__":
    main()
