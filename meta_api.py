import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

API_VERSION = "v25.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
VINSON_ACCOUNT_ID = "act_929653105892474"

AR_TZ = timezone(timedelta(hours=-3))

# Campañas a excluir (contienen estas palabras en el nombre, case-insensitive)
EXCLUDED_KEYWORDS = ["mayorista"]

# Mapeo de categorías por keywords en el nombre del adset
CATEGORY_RULES = [
    ("Camisas", ["camisa"]),
    ("Remeras O", ["remeraso", "remeras_o"]),
    ("Remeras V", ["remerasv", "remeras_v"]),
    ("Wafle", ["wafle"]),
    ("Joggins", ["joggin"]),
    ("Gabardina", ["gabardina"]),
    ("Buzos", ["buzo"]),
]


def classify_category(adset_name):
    """Clasifica un adset en una categoría de producto."""
    name_lower = adset_name.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in name_lower for kw in keywords):
            return category
    return "Otros"


def meta_api_get(endpoint, params=None, access_token=None):
    if params is None:
        params = {}
    params["access_token"] = access_token
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
    all_data = []
    while url:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if "data" not in result:
                    return result
                all_data.extend(result.get("data", []))
                url = result.get("paging", {}).get("next")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"Meta API {e.code}: {body}")
            raise Exception(f"Error de Meta API ({e.code}): {body}")
        except Exception as e:
            logger.error(f"Meta API: {e}")
            raise
    return all_data


def _should_exclude(name):
    name_lower = name.lower()
    return any(kw in name_lower for kw in EXCLUDED_KEYWORDS)


def _extract_purchases_revenue(data):
    """Extrae compras e ingresos. Usa solo 'purchase' para evitar doble conteo con 'omni_purchase'."""
    purchases = 0
    revenue = 0.0
    for action in data.get("actions", []):
        if action.get("action_type") == "purchase":
            purchases += int(action.get("value", 0))
    for av in data.get("action_values", []):
        if av.get("action_type") == "purchase":
            revenue += float(av.get("value", 0))
    return purchases, revenue


def get_campaigns(access_token, since, until):
    """Obtiene campañas activas (sin mayorista) con métricas y desglose por adset."""
    campaigns = meta_api_get(
        f"{VINSON_ACCOUNT_ID}/campaigns",
        params={
            "fields": "name,status,effective_status,objective",
            "filtering": json.dumps([
                {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}
            ]),
            "limit": 50,
        },
        access_token=access_token,
    )
    if not campaigns or not isinstance(campaigns, list):
        return []

    time_range = json.dumps({"since": since, "until": until})
    results = []

    for camp in campaigns:
        camp_name = camp.get("name", "Sin nombre")
        camp_id = camp.get("id")

        # Filtrar campañas excluidas
        if _should_exclude(camp_name):
            continue

        # Insights de la campaña
        insights = meta_api_get(
            f"{camp_id}/insights",
            params={
                "fields": "campaign_name,spend,impressions,clicks,actions,action_values",
                "time_range": time_range,
            },
            access_token=access_token,
        )
        insight = insights[0] if insights and isinstance(insights, list) else {}

        purchases, revenue = _extract_purchases_revenue(insight)
        spend = float(insight.get("spend", 0))
        impressions = int(insight.get("impressions", 0))
        clicks = int(insight.get("clicks", 0))
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        roas = (revenue / spend) if spend > 0 else 0
        cpr = (spend / purchases) if purchases > 0 else 0

        # Desglose por adset
        adsets = _get_adsets_with_insights(camp_id, time_range, access_token)

        # Creativos activos
        creatives = _get_active_creatives(camp_id, access_token)

        results.append({
            "campaign": camp_name,
            "objective": _format_objective(camp.get("objective", "")),
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "purchases": purchases,
            "revenue": revenue,
            "roas": roas,
            "cpr": cpr,
            "creatives": creatives,
            "adsets": adsets,
        })

    return results


def _get_adsets_with_insights(campaign_id, time_range, access_token):
    """Obtiene adsets activos de una campaña con sus métricas y tipo de audiencia."""
    adsets = meta_api_get(
        f"{campaign_id}/adsets",
        params={
            "fields": "name,effective_status,targeting",
            "filtering": json.dumps([
                {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}
            ]),
            "limit": 50,
        },
        access_token=access_token,
    )
    if not adsets or not isinstance(adsets, list):
        return []

    results = []
    for adset in adsets:
        adset_id = adset.get("id")
        adset_name = adset.get("name", "Sin nombre")

        # Audiencia
        audience = _classify_targeting(adset.get("targeting", {}))

        # Insights del adset
        insights = meta_api_get(
            f"{adset_id}/insights",
            params={
                "fields": "spend,impressions,clicks,actions,action_values",
                "time_range": time_range,
            },
            access_token=access_token,
        )
        insight = insights[0] if insights and isinstance(insights, list) else {}

        purchases, revenue = _extract_purchases_revenue(insight)
        spend = float(insight.get("spend", 0))
        impressions = int(insight.get("impressions", 0))
        clicks = int(insight.get("clicks", 0))
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        roas = (revenue / spend) if spend > 0 else 0
        cpr = (spend / purchases) if purchases > 0 else 0

        results.append({
            "adset": adset_name,
            "category": classify_category(adset_name),
            "audience": audience,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "purchases": purchases,
            "revenue": revenue,
            "roas": roas,
            "cpr": cpr,
        })

    return results


def _classify_targeting(targeting):
    if targeting.get("custom_audiences"):
        audiences = targeting["custom_audiences"]
        names = [a.get("name", "").lower() for a in audiences]
        if any("lookalike" in n or "lal" in n for n in names):
            return "Lookalike"
        return "Retargeting"
    elif targeting.get("flexible_spec") or targeting.get("interests"):
        return "Intereses"
    elif targeting.get("behaviors"):
        return "Comportamiento"
    else:
        return "Broad"


def _get_active_creatives(campaign_id, access_token):
    try:
        ads = meta_api_get(
            f"{campaign_id}/ads",
            params={
                "fields": "creative{id,name}",
                "filtering": json.dumps([
                    {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}
                ]),
                "limit": 20,
            },
            access_token=access_token,
        )
        if not ads or not isinstance(ads, list):
            return ""

        creative_names = []
        for ad in ads:
            creative = ad.get("creative", {})
            name = creative.get("name") or creative.get("id", "")
            if name and name not in creative_names:
                creative_names.append(str(name))
        return ", ".join(creative_names[:5])
    except Exception:
        return ""


def get_ads_with_insights(access_token, since, until):
    """Obtiene todos los anuncios activos con métricas y link de preview."""
    campaigns = meta_api_get(
        f"{VINSON_ACCOUNT_ID}/campaigns",
        params={
            "fields": "name,objective",
            "filtering": json.dumps([
                {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}
            ]),
            "limit": 50,
        },
        access_token=access_token,
    )
    if not campaigns or not isinstance(campaigns, list):
        return []

    time_range = json.dumps({"since": since, "until": until})
    results = []

    for camp in campaigns:
        camp_name = camp.get("name", "")
        if _should_exclude(camp_name):
            continue

        camp_id = camp.get("id")
        objective = _format_objective(camp.get("objective", ""))

        # Get ads with creative info and preview link
        ads = meta_api_get(
            f"{camp_id}/ads",
            params={
                "fields": "name,effective_status,creative{id,name,effective_object_story_id},adset{name},preview_shareable_link",
                "filtering": json.dumps([
                    {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}
                ]),
                "limit": 50,
            },
            access_token=access_token,
        )
        if not ads or not isinstance(ads, list):
            continue

        for ad in ads:
            ad_id = ad.get("id")
            ad_name = ad.get("name", "Sin nombre")
            adset_name = ad.get("adset", {}).get("name", "—")
            creative = ad.get("creative", {})
            creative_name = creative.get("name") or creative.get("id", "—")
            preview_link = ad.get("preview_shareable_link", "")

            # Insights del anuncio
            insights = meta_api_get(
                f"{ad_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,actions,action_values",
                    "time_range": time_range,
                },
                access_token=access_token,
            )
            insight = insights[0] if insights and isinstance(insights, list) else {}

            purchases, revenue = _extract_purchases_revenue(insight)
            spend = float(insight.get("spend", 0))
            impressions = int(insight.get("impressions", 0))
            clicks = int(insight.get("clicks", 0))
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            roas = (revenue / spend) if spend > 0 else 0
            cpr = (spend / purchases) if purchases > 0 else 0

            results.append({
                "ad_name": ad_name,
                "campaign": camp_name,
                "adset": adset_name,
                "objective": objective,
                "creative": creative_name,
                "preview_link": preview_link,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "purchases": purchases,
                "revenue": revenue,
                "roas": roas,
                "cpr": cpr,
            })

    return results


def _format_objective(objective):
    mapping = {
        "OUTCOME_SALES": "Conversiones",
        "OUTCOME_TRAFFIC": "Tráfico",
        "OUTCOME_AWARENESS": "Alcance",
        "OUTCOME_ENGAGEMENT": "Interacción",
        "OUTCOME_LEADS": "Leads",
        "OUTCOME_APP_PROMOTION": "App",
        "CONVERSIONS": "Conversiones",
        "LINK_CLICKS": "Tráfico",
        "REACH": "Alcance",
        "BRAND_AWARENESS": "Alcance",
        "POST_ENGAGEMENT": "Interacción",
        "LEAD_GENERATION": "Leads",
        "MESSAGES": "Mensajes",
    }
    return mapping.get(objective, objective.replace("OUTCOME_", "").replace("_", " ").title())
