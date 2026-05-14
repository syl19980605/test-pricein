import asyncio

from backend.agent.llm import complete_json
from backend.models.schemas import StrategyCard
from backend.services.market_data import ASSET_REGISTRY, market_data_service
from backend.services.technical import technical_service


RISK_PROFILE = {
    "conservative": "保守型：优先低波动、看重资本保全，可接受较低收益",
    "moderate": "稳健型：在收益与风险间平衡，可接受中等波动",
    "aggressive": "进取型：追求高收益，可承受较大回撤",
}


def _build_strategy_sync(symbols: list[str], risk_level: str, context: str) -> dict:
    asset_lines = []
    for s in symbols:
        meta = ASSET_REGISTRY.get(s, {})
        asset_lines.append(f"- {s} ({meta.get('name', s)}, {meta.get('asset_class', 'unknown')})")
    assets_text = "\n".join(asset_lines)

    prompt = f"""为以下头部资产设计一个中长线投资组合策略。

候选资产:
{assets_text}

风险等级: {RISK_PROFILE.get(risk_level, RISK_PROFILE['moderate'])}

实时数据参考:
{context}

要求:
1. 给出每个资产的配比（allocation，总和为1.0）
2. 估算组合的预期年化收益(expected_return_annual，小数如0.15)、最大回撤(max_drawdown，小数如0.20)、夏普比率(sharpe_ratio)
3. 给出3条进场条件(entry_conditions)和3条出场条件(exit_conditions)，要具体、可执行、纪律化（含止盈止损位）
4. reasoning：2-3句中文说明组合构建逻辑
5. title：一个简洁的中文策略名称

返回 JSON:
{{
  "title": "...",
  "allocation": {{"SYMBOL": 0.x, ...}},
  "expected_return_annual": 0.x,
  "max_drawdown": 0.x,
  "sharpe_ratio": x.x,
  "reasoning": "...",
  "entry_conditions": ["...", "...", "..."],
  "exit_conditions": ["...", "...", "..."]
}}"""

    return complete_json(prompt, "你是一个专业的投资组合策略师，注重风险纪律。", 1536)


class StrategyGenerator:
    async def generate(
        self, symbols: list[str], risk_level: str = "moderate"
    ) -> StrategyCard:
        valid_symbols = [s for s in symbols if s in ASSET_REGISTRY]
        if not valid_symbols:
            valid_symbols = symbols

        # 拉取实时数据作为上下文
        context_parts = []
        for s in valid_symbols:
            try:
                price = await market_data_service.get_current_price(s)
                ind = await technical_service.calculate_all(s)
                context_parts.append(
                    f"{s}: 价格 {price['current_price']}, 24h {price['change_24h_pct']}%, "
                    f"RSI {ind.rsi_14}, MACD柱 {ind.macd_histogram}"
                )
            except Exception:
                context_parts.append(f"{s}: 数据获取失败")
        context = "\n".join(context_parts)

        result = await asyncio.get_event_loop().run_in_executor(
            None, _build_strategy_sync, valid_symbols, risk_level, context
        )

        if not result:
            # 回退：等权配置
            equal = round(1.0 / len(valid_symbols), 3)
            return StrategyCard(
                title="等权头部资产组合",
                symbols=valid_symbols,
                allocation={s: equal for s in valid_symbols},
                risk_level=risk_level,
                reasoning="策略生成服务暂时不可用，返回等权配置作为基线。",
                entry_conditions=["分批建仓，单次不超过计划仓位的1/3"],
                exit_conditions=["单一资产回撤达 -10% 触发止损", "组合收益达 +20% 部分止盈"],
            )

        allocation = result.get("allocation", {})
        # 归一化
        total = sum(allocation.values()) or 1.0
        allocation = {k: round(v / total, 3) for k, v in allocation.items()}

        return StrategyCard(
            title=result.get("title", "头部资产组合策略"),
            symbols=list(allocation.keys()) or valid_symbols,
            allocation=allocation,
            expected_return_annual=result.get("expected_return_annual"),
            max_drawdown=result.get("max_drawdown"),
            sharpe_ratio=result.get("sharpe_ratio"),
            risk_level=risk_level,
            reasoning=result.get("reasoning", ""),
            entry_conditions=result.get("entry_conditions", []),
            exit_conditions=result.get("exit_conditions", []),
        )


strategy_generator = StrategyGenerator()
