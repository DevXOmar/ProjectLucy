from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
import shap
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import text
from sqlalchemy.orm import Session
from statsmodels.tsa.holtwinters import ExponentialSmoothing


# Comparison-shopped items are commodities a customer can price-check elsewhere,
# so raising price on them is risky. Services and one-off durables (haircut,
# facial, cricket bat, saree) are far less comparison-shopped, which is what the
# pricing recommendation keys off. Keyword list spans all six categories.
COMPARISON_SHOPPED_KEYWORDS = [
    # Kirana staples
    "milk",
    "salt",
    "maggi",
    "oil",
    "soda",
    "colgate",
    "atta",
    "surf",
    "biscuits",
    "tea",
    # Chemist essentials
    "paracetamol",
    "sanitizer",
    "ors",
    "band-aid",
    "multivitamin",
    # Distributor bulk staples
    "rice",
    "wheat",
    "sugar",
    # Sports and clothing commodities
    "football",
    "yoga mat",
    "t-shirt",
    "jeans",
]


def tier_for_visits(visits: int) -> tuple[str, int | None]:
    if visits < 3:
        return "New", 3
    if visits < 8:
        return "Level 1 Regular", 8
    if visits < 15:
        return "Level 2 Regular", 15
    return "VIP", None


def pct(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(float(value), 4)


@dataclass
class MLCache:
    relationships: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    call_lists: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    pulses: dict[int, dict[str, Any]] = field(default_factory=dict)
    pricing: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    rewards: dict[int, dict[str, Any]] = field(default_factory=dict)
    merchant_rewards: dict[int, dict[str, Any]] = field(default_factory=dict)
    loans: dict[int, dict[str, Any]] = field(default_factory=dict)
    recomputed_at: str | None = None
    timings: dict[str, float] = field(default_factory=dict)


class MLEngine:
    def __init__(self) -> None:
        self.cache = MLCache()

    def recompute(self, db: Session) -> dict[str, Any]:
        started = time.perf_counter()
        tx = pd.read_sql(
            text(
                """
                select
                    t.id,
                    t.customer_id,
                    c.name as customer_name,
                    t.merchant_id,
                    m.name as merchant_name,
                    m.category as merchant_category,
                    t.timestamp,
                    t.amount
                from transactions t
                join customers c on c.id = t.customer_id
                join merchants m on m.id = t.merchant_id
                """
            ),
            db.bind,
            parse_dates=["timestamp"],
        )
        items = pd.read_sql(
            text(
                """
                select
                    ti.transaction_id,
                    t.merchant_id,
                    ti.sku,
                    ti.quantity,
                    ti.unit_price
                from transaction_items ti
                join transactions t on t.id = ti.transaction_id
                """
            ),
            db.bind,
        )
        prices = pd.read_sql(
            text(
                """
                select
                    p.merchant_id,
                    m.name as merchant_name,
                    m.category,
                    p.sku,
                    p.price
                from merchant_sku_prices p
                join merchants m on m.id = p.merchant_id
                """
            ),
            db.bind,
        )
        merchants = pd.read_sql(text("select id, name, category, locality from merchants"), db.bind)
        # Illustrative demo pricing, not live data: seeded prices for the fictional
        # comparison platforms shown in Market Match. Never feeds any recommendation.
        demo_platforms = pd.read_sql(
            text("select sku, platform, price, was_price from demo_platform_prices"),
            db.bind,
        )

        timings: dict[str, float] = {}
        step = time.perf_counter()
        relationships, call_lists = self._build_relationships(tx)
        timings["relationship_seconds"] = round(time.perf_counter() - step, 3)

        step = time.perf_counter()
        pricing = self._build_pricing(tx, items, prices, merchants, demo_platforms)
        timings["pricing_seconds"] = round(time.perf_counter() - step, 3)

        step = time.perf_counter()
        pulses = self._build_pulses(tx, relationships, call_lists)
        timings["pulse_seconds"] = round(time.perf_counter() - step, 3)

        step = time.perf_counter()
        rewards, merchant_rewards = self._build_rewards(tx, relationships)
        timings["rewards_seconds"] = round(time.perf_counter() - step, 3)

        step = time.perf_counter()
        loans = self._build_loans(tx, relationships, merchants)
        timings["loan_seconds"] = round(time.perf_counter() - step, 3)

        self.cache = MLCache(
            relationships=relationships,
            call_lists=call_lists,
            pulses=pulses,
            pricing=pricing,
            rewards=rewards,
            merchant_rewards=merchant_rewards,
            loans=loans,
            recomputed_at=pd.Timestamp.now().isoformat(timespec="seconds"),
            timings=timings | {"total_seconds": round(time.perf_counter() - started, 3)},
        )
        print(f"ML recompute complete: {self.cache.timings}")
        return {"recomputed_at": self.cache.recomputed_at, "timings": self.cache.timings}

    def _build_relationships(self, tx: pd.DataFrame) -> tuple[dict[tuple[int, int], dict[str, Any]], dict[int, list[dict[str, Any]]]]:
        if tx.empty:
            return {}, {}

        work = tx.copy()
        work["pair_id"] = work["customer_id"].astype(str) + ":" + work["merchant_id"].astype(str)
        pair_counts = work.groupby("pair_id").size()
        work = work[work["pair_id"].isin(pair_counts[pair_counts >= 2].index)]
        if work.empty:
            return {}, {}

        summary = summary_data_from_transaction_data(
            work,
            customer_id_col="pair_id",
            datetime_col="timestamp",
            monetary_value_col="amount",
            observation_period_end=work["timestamp"].max() + timedelta(days=1),
        )
        summary = summary.replace([np.inf, -np.inf], np.nan).fillna(0)
        summary = summary[(summary["frequency"] >= 1) & (summary["monetary_value"] > 0)]

        bgf = BetaGeoFitter(penalizer_coef=0.05)
        bgf.fit(summary["frequency"], summary["recency"], summary["T"])
        p_alive = pd.Series(
            bgf.conditional_probability_alive(summary["frequency"], summary["recency"], summary["T"]),
            index=summary.index,
        )

        ggf = GammaGammaFitter(penalizer_coef=0.05)
        ggf.fit(summary["frequency"], summary["monetary_value"])
        clv = pd.Series(
            ggf.customer_lifetime_value(
                bgf,
                summary["frequency"],
                summary["recency"],
                summary["T"],
                summary["monetary_value"],
                time=6,
                discount_rate=0.01,
            ),
            index=summary.index,
        )

        visits = work.groupby(["customer_id", "merchant_id"]).agg(
            visit_count=("id", "count"),
            last_visit_date=("timestamp", "max"),
            customer_name=("customer_name", "first"),
            merchant_name=("merchant_name", "first"),
        )
        today = work["timestamp"].max().normalize() + timedelta(days=1)
        relationships: dict[tuple[int, int], dict[str, Any]] = {}
        for pair_id, row in summary.iterrows():
            customer_id, merchant_id = [int(part) for part in str(pair_id).split(":")]
            visit = visits.loc[(customer_id, merchant_id)]
            visit_count = int(visit["visit_count"])
            tier, next_threshold = tier_for_visits(visit_count)
            gap = max(0, (next_threshold or visit_count) - visit_count)
            relationships[(customer_id, merchant_id)] = {
                "customer_id": customer_id,
                "merchant_id": merchant_id,
                "customer_name": visit["customer_name"],
                "merchant_name": visit["merchant_name"],
                "visit_count": visit_count,
                "tier": tier,
                "next_tier_threshold": next_threshold,
                "visits_to_next_tier": gap,
                "p_alive": pct(float(p_alive.loc[pair_id])),
                "predicted_clv": round(max(0.0, float(clv.loc[pair_id])), 2),
                "postpaid_eligible": bool(visit_count > 8 and float(p_alive.loc[pair_id]) > 0.6),
                "last_visit_date": visit["last_visit_date"].date().isoformat(),
                "days_since_last_visit": int((today - visit["last_visit_date"].normalize()).days),
            }

        call_lists: dict[int, list[dict[str, Any]]] = {}
        for data in relationships.values():
            if data["p_alive"] < 0.4:
                call_lists.setdefault(data["merchant_id"], []).append(data)
        for merchant_id, rows in call_lists.items():
            call_lists[merchant_id] = sorted(rows, key=lambda item: (item["p_alive"], -item["predicted_clv"]))[:20]
        return relationships, call_lists

    def _build_pulses(
        self,
        tx: pd.DataFrame,
        relationships: dict[tuple[int, int], dict[str, Any]],
        call_lists: dict[int, list[dict[str, Any]]],
    ) -> dict[int, dict[str, Any]]:
        pulses: dict[int, dict[str, Any]] = {}
        if tx.empty:
            return pulses
        tx = tx.copy()
        tx["date"] = tx["timestamp"].dt.normalize()
        tx["hour"] = tx["timestamp"].dt.hour
        last_day = tx["date"].max()

        for merchant_id, merchant_tx in tx.groupby("merchant_id"):
            daily = merchant_tx.groupby("date")["amount"].sum().asfreq("D", fill_value=0)
            fitted = daily.rolling(7, min_periods=1).mean()
            forecast_values = np.repeat(float(daily.tail(14).mean()), 30)
            residual_std = float((daily - fitted).std() or daily.std() or 1)
            try:
                model = ExponentialSmoothing(
                    daily,
                    trend="add",
                    seasonal="add",
                    seasonal_periods=7,
                    initialization_method="estimated",
                )
                fit = model.fit(optimized=True)
                fitted = fit.fittedvalues
                forecast_values = np.maximum(0, fit.forecast(30).to_numpy())
                residual_std = float((daily - fitted).std() or residual_std)
            except Exception as exc:
                print(f"Pulse fallback for merchant {merchant_id}: {exc}")

            future_dates = pd.date_range(last_day + timedelta(days=1), periods=30, freq="D")
            forecast = [
                {
                    "date": date.date().isoformat(),
                    "value": round(float(value), 2),
                    "lower": round(max(0.0, float(value) - 1.96 * residual_std), 2),
                    "upper": round(float(value) + 1.96 * residual_std, 2),
                }
                for date, value in zip(future_dates, forecast_values)
            ]

            residual = daily - fitted
            rolling_std = residual.rolling(21, min_periods=7).std().replace(0, np.nan)
            recent = residual.tail(14)
            anomaly = None
            flagged = recent[(recent.abs() > (2 * rolling_std.loc[recent.index]).fillna(residual_std))]
            if not flagged.empty:
                date = flagged.abs().idxmax()
                severity = "high" if abs(flagged.loc[date]) > 3 * residual_std else "medium"
                direction = "up" if flagged.loc[date] > 0 else "down"
                anomaly = {
                    "description": f"{date.strftime('%A')} revenue was {direction} {round(abs(flagged.loc[date]))} vs the fitted weekly pattern.",
                    "severity": severity,
                }

            same_weekday_note = self._same_weekday_drop(daily)
            if same_weekday_note:
                anomaly = {"description": same_weekday_note, "severity": "medium"}

            hours = merchant_tx.groupby("hour").size().sort_values(ascending=False).head(2)
            busiest_hours = [f"{int(hour)}:00" for hour in hours.index]
            merchant_relationships = [data for data in relationships.values() if data["merchant_id"] == int(merchant_id)]
            top_regulars = sorted(merchant_relationships, key=lambda item: (item["visit_count"], item["predicted_clv"]), reverse=True)[:5]
            top_regular_name = top_regulars[0]["customer_name"] if top_regulars else "No regular yet"
            forecast_revenue = sum(item["value"] for item in forecast)
            # Demo assumption: keep 20% of forecasted 30-day revenue liquid for supplier payments before the 5th.
            reserve = round(forecast_revenue * 0.2)
            cashflow_note = f"Set aside ~₹{reserve:,} before the 5th based on your typical spend pattern."
            anomaly_sentence = anomaly["description"] if anomaly else "No sharp revenue anomaly is showing in the recent window."
            briefing = (
                f"Your busiest hours are {', '.join(busiest_hours) or 'not available'}. "
                f"{top_regular_name} is your top regular this month. "
                f"{anomaly_sentence} {cashflow_note}"
            )
            pulses[int(merchant_id)] = {
                "forecast_30d": forecast,
                "busiest_hours": busiest_hours,
                "top_regulars": top_regulars,
                "anomaly": anomaly,
                "churn_alerts": call_lists.get(int(merchant_id), []),
                "cashflow_note": cashflow_note,
                "briefing": briefing,
            }
        return pulses

    def _same_weekday_drop(self, daily: pd.Series) -> str | None:
        if len(daily) < 35:
            return None
        latest = daily.index.max()
        weekday = latest.weekday()
        same_weekday = daily[daily.index.weekday == weekday]
        if len(same_weekday) < 5:
            return None
        recent_value = float(same_weekday.iloc[-1])
        historical = same_weekday.iloc[:-1]
        mean = float(historical.mean())
        if mean <= 0:
            return None
        drop = (mean - recent_value) / mean
        if drop > 0.25:
            return f"Your {latest.strftime('%A')} sales are down {round(drop * 100)}% vs your {latest.strftime('%A')} average."
        return None

    def _build_pricing(
        self,
        tx: pd.DataFrame,
        items: pd.DataFrame,
        prices: pd.DataFrame,
        merchants: pd.DataFrame,
        demo_platforms: pd.DataFrame | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        if tx.empty or prices.empty:
            return {}

        tx = tx.copy()
        tx["is_weekend"] = tx["timestamp"].dt.weekday >= 5
        base = tx.groupby("merchant_id").agg(
            avg_basket=("amount", "mean"),
            tx_count=("id", "count"),
            unique_customers=("customer_id", "nunique"),
            weekend_ratio=("is_weekend", "mean"),
        )
        visit_counts = tx.groupby(["merchant_id", "customer_id"]).size().groupby("merchant_id").agg(["mean", "std"]).fillna(0)
        categories = tx.pivot_table(index="merchant_id", columns="merchant_category", values="amount", aggfunc="sum", fill_value=0)
        category_mix = categories.div(categories.sum(axis=1), axis=0).fillna(0)
        features = base.join(visit_counts, how="left").join(category_mix, how="left").fillna(0)
        features = features.reindex(merchants["id"]).fillna(0)
        matrix = (features - features.mean()) / features.std(ddof=0).replace(0, 1)
        n_components = max(1, min(5, matrix.shape[1] - 1, matrix.shape[0] - 1))
        embeddings = TruncatedSVD(n_components=n_components, random_state=42).fit_transform(matrix)

        merchant_ids = merchants["id"].tolist()
        id_to_index = {merchant_id: idx for idx, merchant_id in enumerate(merchant_ids)}
        merchant_category = merchants.set_index("id")["category"].to_dict()
        pricing: dict[int, list[dict[str, Any]]] = {}
        similarity = cosine_similarity(embeddings)

        # Illustrative demo pricing, not live data. Grouped once per SKU so every
        # merchant selling that SKU sees the same stable comparison rows.
        demo_by_sku: dict[str, list[dict[str, Any]]] = {}
        if demo_platforms is not None and not demo_platforms.empty:
            for sku, group in demo_platforms.groupby("sku"):
                demo_by_sku[str(sku)] = [
                    {
                        "platform": str(row["platform"]),
                        "price": round(float(row["price"]), 2),
                        "was_price": round(float(row["was_price"]), 2),
                        "illustrative": True,
                    }
                    for _, row in group.iterrows()
                ]

        for merchant_id in merchant_ids:
            same_category = [
                other_id
                for other_id in merchant_ids
                if other_id != merchant_id and merchant_category[other_id] == merchant_category[merchant_id]
            ]
            neighbors = sorted(
                same_category,
                key=lambda other_id: similarity[id_to_index[merchant_id], id_to_index[other_id]],
                reverse=True,
            )[:5]
            rows = []
            own_prices = prices[prices["merchant_id"] == merchant_id]
            for _, price in own_prices.iterrows():
                sku = price["sku"]
                neighbor_rows = prices[(prices["merchant_id"].isin(neighbors)) & (prices["sku"] == sku)]
                neighbor_prices = neighbor_rows["price"]
                benchmark = float(neighbor_prices.mean()) if not neighbor_prices.empty else float(price["price"])
                your_price = float(price["price"])
                gap = (your_price - benchmark) / benchmark if benchmark else 0
                flag = "red" if gap > 0.05 else "green"
                comparison_shopped = any(keyword in sku.lower() for keyword in COMPARISON_SHOPPED_KEYWORDS)
                # Rule-based classification/recommendation: branded commodity SKUs are comparison-shopped;
                # services and less comparable items can tolerate modest price headroom.
                suggested_points = int(max(5, round(gap * your_price / 2))) if flag == "red" and comparison_shopped else 0
                if flag == "red" and comparison_shopped:
                    recommendation = f"Hold price, offer {suggested_points} Loyalty Points instead."
                elif flag == "red":
                    recommendation = "Small headroom to raise price safely."
                else:
                    recommendation = "No action needed, you're competitive."
                rows.append(
                    {
                        "sku": sku,
                        "your_price": round(your_price, 2),
                        "benchmark_price": round(benchmark, 2),
                        "peer_count": int(len(neighbor_rows)),
                        "peer_prices": [
                            {
                                "merchant_id": int(row["merchant_id"]),
                                "label": f"Nearby Shop {chr(65 + index)}",
                                "price": round(float(row["price"]), 2),
                            }
                            for index, (_, row) in enumerate(neighbor_rows.head(5).iterrows())
                        ],
                        # Illustrative demo pricing, not live data - see DEMO_PLATFORMS in seed.py.
                        "demo_platforms": demo_by_sku.get(str(sku), []),
                        "flag": flag,
                        "comparison_shopped": bool(comparison_shopped),
                        "recommendation": recommendation,
                        "suggested_points": suggested_points,
                    }
                )
            pricing[int(merchant_id)] = rows
        return pricing

    def _build_rewards(
        self,
        tx: pd.DataFrame,
        relationships: dict[tuple[int, int], dict[str, Any]],
    ) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
        if tx.empty:
            return {}, {}
        rng = np.random.default_rng(20260821)
        arms = np.array([1.0, 1.5, 2.0, 3.0])
        tier_bias = {
            "New": np.array([0.08, 0.10, 0.12, 0.11]),
            "Level 1 Regular": np.array([0.10, 0.14, 0.18, 0.17]),
            "Level 2 Regular": np.array([0.12, 0.17, 0.24, 0.27]),
            "VIP": np.array([0.14, 0.19, 0.27, 0.34]),
        }
        alpha = {tier: np.ones(len(arms)) for tier in tier_bias}
        beta = {tier: np.ones(len(arms)) for tier in tier_bias}
        redemption_stats: dict[str, dict[float, float]] = {}

        # Synthetic, reproducible reward observations for a Thompson Sampling demo:
        # redemption probability is a seeded function of loyalty tier and multiplier arm.
        for tier, probs in tier_bias.items():
            for _ in range(600):
                for index, probability in enumerate(probs):
                    redeemed = rng.random() < probability
                    alpha[tier][index] += int(redeemed)
                    beta[tier][index] += int(not redeemed)
            redemption_stats[tier] = {
                float(arm): round(float(alpha[tier][idx] / (alpha[tier][idx] + beta[tier][idx])), 3)
                for idx, arm in enumerate(arms)
            }

        latest_tx = tx.sort_values("timestamp").groupby("customer_id").tail(1).set_index("customer_id")
        customer_best: dict[int, dict[str, Any]] = {}
        for relationship in relationships.values():
            current = customer_best.get(relationship["customer_id"])
            if not current or relationship["visit_count"] > current["visit_count"]:
                customer_best[relationship["customer_id"]] = relationship

        rewards: dict[int, dict[str, Any]] = {}
        for customer_id, row in latest_tx.iterrows():
            relationship = customer_best.get(int(customer_id))
            tier = relationship["tier"] if relationship else "New"
            samples = rng.beta(alpha[tier], beta[tier])
            arm = float(arms[int(np.argmax(samples))])
            best_observed_arm = max(redemption_stats[tier], key=redemption_stats[tier].get)
            base_points = max(1, int(float(row["amount"]) // 10))
            points_earned = int(round(base_points * arm))
            rewards[int(customer_id)] = {
                "customer_id": int(customer_id),
                "tier": tier,
                "selected_arm": f"{arm:g}x",
                "multiplier": arm,
                "last_purchase_amount": round(float(row["amount"]), 2),
                "points_earned": points_earned,
                "points_balance": 520 + int(customer_id) * 7 % 430 + points_earned,
                "redemption_rates": redemption_stats[tier],
                "explanation": (
                    f"This offer was selected because customers at your loyalty tier redeem "
                    f"{best_observed_arm:g}x offers most often in the seeded bandit history."
                ),
            }

        tx_month = tx[tx["timestamp"] >= tx["timestamp"].max() - timedelta(days=30)].copy()
        merchant_rewards: dict[int, dict[str, Any]] = {}
        for merchant_id, merchant_tx in tx_month.groupby("merchant_id"):
            points = 0
            for _, row in merchant_tx.iterrows():
                reward = rewards.get(int(row["customer_id"]))
                multiplier = reward["multiplier"] if reward else 1.0
                points += int(round(max(1, float(row["amount"]) // 10) * multiplier))
            estimated_cost = round(points * 0.25, 2)
            retained_revenue = round(
                sum(
                    rel["predicted_clv"] * max(0, rel["p_alive"] - 0.4) * 0.08
                    for rel in relationships.values()
                    if rel["merchant_id"] == int(merchant_id)
                ),
                2,
            )
            merchant_rewards[int(merchant_id)] = {
                "merchant_id": int(merchant_id),
                "points_issued_this_month": points,
                "estimated_cost": estimated_cost,
                "estimated_retained_revenue": retained_revenue,
                "assumption": "Simplified estimate: 1 point costs ₹0.25 and retained revenue is 8% of healthy CLV above P(alive)=0.4.",
            }
        return rewards, merchant_rewards

    def _build_loans(
        self,
        tx: pd.DataFrame,
        relationships: dict[tuple[int, int], dict[str, Any]],
        merchants: pd.DataFrame,
    ) -> dict[int, dict[str, Any]]:
        if tx.empty:
            return {}
        tx = tx.copy()
        tx["date"] = tx["timestamp"].dt.normalize()
        tx["hour"] = tx["timestamp"].dt.hour
        rows = []
        for merchant_id, merchant_tx in tx.groupby("merchant_id"):
            daily = merchant_tx.groupby("date")["amount"].sum().asfreq("D", fill_value=0)
            x = np.arange(len(daily))
            slope = float(np.polyfit(x, daily.to_numpy(), 1)[0]) if len(daily) > 1 else 0.0
            mean_revenue = float(daily.mean())
            steady_volume = float(1 / (1 + (daily.std() / (mean_revenue + 1))))
            evening_share = float((merchant_tx["hour"] >= 18).mean())
            merchant_relationships = [rel for rel in relationships.values() if rel["merchant_id"] == int(merchant_id)]
            regulars_count = sum(1 for rel in merchant_relationships if rel["visit_count"] >= 8)
            weighted_health = float(np.mean([rel["p_alive"] * min(rel["visit_count"], 20) / 20 for rel in merchant_relationships]) if merchant_relationships else 0)
            rows.append(
                {
                    "merchant_id": int(merchant_id),
                    "steady_volume": steady_volume,
                    "evening_share": evening_share,
                    "revenue_trend_slope": slope,
                    "regulars_count": regulars_count,
                    "weighted_customer_health": weighted_health,
                    "mean_revenue": mean_revenue,
                }
            )
        features = pd.DataFrame(rows).set_index("merchant_id")

        score = (
            features["steady_volume"] * 34
            + np.clip(features["revenue_trend_slope"], -20, 40) * 0.35
            + np.clip(features["regulars_count"], 0, 80) * 0.55
            + features["weighted_customer_health"] * 30
            + features["evening_share"] * 12
        )
        rng = np.random.default_rng(20260821)
        noisy_score = score + rng.normal(0, 3, len(score))
        # Synthetic labels for demo training only: loan tier eligibility is generated
        # from stable volume, positive trend, regulars count, and customer-base health
        # plus small noise. The cut points are the 33rd/66th percentiles of the
        # network's own score distribution rather than fixed numbers, so all three
        # tiers stay populated as the merchant mix changes - with 24 merchants sharing
        # the customer base, fixed cut points collapsed every merchant into one tier.
        lower_cut, upper_cut = (float(value) for value in np.quantile(noisy_score, [1 / 3, 2 / 3]))
        upper_cut = max(upper_cut, lower_cut + 1e-6)
        labels = pd.cut(noisy_score, bins=[-np.inf, lower_cut, upper_cut, np.inf], labels=[0, 1, 2]).astype(int)
        model = RandomForestClassifier(n_estimators=120, random_state=42, min_samples_leaf=2)
        model.fit(features, labels)
        probabilities = model.predict_proba(features)
        predictions = model.predict(features)

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(features)
        loans: dict[int, dict[str, Any]] = {}
        feature_labels = {
            "steady_volume": "steady daily volume",
            "evening_share": "evening-hour share",
            "revenue_trend_slope": "revenue trend",
            "regulars_count": "regular customer count",
            "weighted_customer_health": "Loyalty health",
            "mean_revenue": "average daily revenue",
        }
        # Coaching targets a merchant compares against. The count-based and revenue-based
        # ones are network-relative so they stay reachable at any dataset scale.
        thresholds = {
            "steady_volume": 0.78,
            "evening_share": 0.45,
            "revenue_trend_slope": 3.0,
            "regulars_count": float(features["regulars_count"].quantile(0.75)),
            "weighted_customer_health": 0.45,
            "mean_revenue": features["mean_revenue"].quantile(0.65),
        }

        for row_index, merchant_id in enumerate(features.index):
            tier = int(predictions[row_index])
            tier_name = ["Starter", "Growth Ready", "Priority Eligible"][tier]
            next_tier = min(2, tier + 1)
            class_positions = {int(label): index for index, label in enumerate(model.classes_)}
            next_class_position = class_positions.get(next_tier, probabilities.shape[1] - 1)
            next_probability = float(probabilities[row_index][next_class_position]) if next_tier in class_positions else 1.0
            progress = int(min(98, max(12, round((score.loc[merchant_id] / 75) * 100))))
            if isinstance(shap_values, list):
                class_values = shap_values[next_class_position]
            elif getattr(shap_values, "ndim", 0) == 3:
                class_values = shap_values[:, :, next_class_position]
            else:
                class_values = shap_values
            merchant_shap = class_values[row_index]
            candidates = []
            for feature, contribution in zip(features.columns, merchant_shap):
                current = float(features.loc[merchant_id, feature])
                threshold = float(thresholds[feature])
                if current < threshold:
                    candidates.append((abs(float(contribution)), feature, current, threshold))
            candidates = sorted(candidates, reverse=True)[:2]
            coaching = []
            for _, feature, current, threshold in candidates:
                label = feature_labels[feature]
                if feature == "regulars_count":
                    coaching.append(f"Add {math.ceil(threshold - current)} more regular customers to strengthen the next loan tier.")
                elif feature == "evening_share":
                    coaching.append("Two more weeks of steady evening volume can improve your next-tier signal.")
                elif feature == "revenue_trend_slope":
                    coaching.append("Keep weekly revenue moving upward; a small positive trend is the next unlock.")
                else:
                    coaching.append(f"Improve {label} toward {threshold:.2f} to move closer to the next tier.")
            if not coaching:
                coaching = ["You are already tracking strongly across the top loan-readiness factors."]
            loans[int(merchant_id)] = {
                "merchant_id": int(merchant_id),
                "tier": tier_name,
                "tier_index": tier,
                "progress_to_next_tier": progress,
                "next_tier_probability": round(next_probability, 3),
                "coaching": coaching,
                "top_factors": [
                    {"feature": feature_labels[feature], "value": round(float(features.loc[merchant_id, feature]), 3)}
                    for _, feature, _, _ in candidates
                ],
            }
        return loans


ml_engine = MLEngine()
