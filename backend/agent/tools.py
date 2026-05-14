BOBBY_TOOLS = [
    {
        "name": "get_asset_price",
        "description": "获取某个资产的实时价格、24小时涨跌幅、成交量和市值。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "资产代码，如 AAPL、BTC-USD、600519.SS、GC=F",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_technical_indicators",
        "description": "获取某个资产的技术指标：RSI、MACD、布林带、均线(SMA/EMA)、ATR等。用于技术面分析。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "资产代码"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "analyze_news_sentiment",
        "description": "获取并分析某个资产的近期新闻，返回每条新闻的情绪分(-1到1)和整体情绪倾向。用于消息面分析。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "资产代码"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "generate_strategy_card",
        "description": "为一组资产生成一个投资组合策略卡片，包含配比、预期收益、最大回撤、夏普比率、进场/出场条件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "资产代码列表",
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["conservative", "moderate", "aggressive"],
                    "description": "风险等级",
                },
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "begin_analysis",
        "description": (
            "【统一分析流程的第一步 —— 入口工具】当用户问到任意单个标的时，必须先调用本工具。"
            "典型触发：「X 值不值得买」「X 怎么样」「我看到 X 的某条消息」「帮我分析 X」等 —— "
            "只要是针对某个标的的问询/求分析，都先走这里。"
            "它只做一件事：向用户询问对该标的的持有期预期（持有期是整条分析的前置参数 —— "
            "「定价程度」是 horizon-conditional 的，先有持有期才能往下分析）。"
            "调用后会自动展示让用户选持有期的交互卡片，你只需简短引导，不要替用户选。"
            "如果用户提到了具体消息就填 news_event；如果用户表达了利好/利空判断就填 user_hypothesis —— "
            "这两个都是可选的，用户没提就不填。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "资产代码"},
                "news_event": {
                    "type": "string",
                    "description": "（可选）用户提到的具体新闻/消息内容，没提到就不填",
                },
                "user_hypothesis": {
                    "type": "string",
                    "description": "（可选）用户对影响方向的判断，如'利好'/'利空'，用户没表态就不填",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "analyze_asset",
        "description": (
            "统一分析流程的核心工具。在用户通过 begin_analysis 选定持有期之后调用。它会综合："
            "① 拆解驱动因素去预测市场（Polymarket）搜索、按持有期加权聚合出投资者「预期」的定价程度；"
            "② 技术面+情绪面+预测市场 综合成买卖信号；"
            "③ 若用户提到了具体消息，额外做该消息的影响分析（用户没给判断方向时由你自己判断）；"
            "④ 综合得出买入信号 vs 卖出信号哪个更强。"
            "horizon 必填 —— 没有持有期不能调用本工具，必须先经过 begin_analysis。"
            "news_event / user_hypothesis 可选：用户提到具体消息才填 news_event，用户表态了才填 user_hypothesis。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "资产代码"},
                "horizon": {
                    "type": "string",
                    "enum": ["short", "mid", "long"],
                    "description": "用户的投资持有期（来自 begin_analysis 后用户的选择）：short=短期(数天-数周), mid=中长线(数月), long=长期(一年以上)",
                },
                "news_event": {
                    "type": "string",
                    "description": "（可选）用户提到的具体新闻/消息内容",
                },
                "user_hypothesis": {
                    "type": "string",
                    "description": "（可选）用户对影响方向的判断，如'利好'/'利空'",
                },
            },
            "required": ["symbol", "horizon"],
        },
    },
    {
        "name": "create_monitor",
        "description": (
            "为某个标的创建一个持续监控。监控会定期刷新该标的的价格影响消息、综合信号及其被定价程度。"
            "当用户在分析后表示要「创建监控」时调用。刷新周期由用户选择（分钟数）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "资产代码"},
                "thesis": {
                    "type": "string",
                    "description": "用户对该标的的判断逻辑（来自之前的对话）",
                },
                "direction": {
                    "type": "string",
                    "enum": ["bullish", "bearish"],
                    "description": "用户判断的方向",
                },
                "horizon": {
                    "type": "string",
                    "enum": ["short", "mid", "long"],
                    "description": "用户的投资持有期（场景流前面已确定）",
                },
                "refresh_interval_min": {
                    "type": "integer",
                    "description": "刷新周期（分钟）。如每小时=60，每4小时=240，每天=1440",
                },
            },
            "required": ["symbol", "thesis", "direction", "horizon", "refresh_interval_min"],
        },
    },
    {
        "name": "manage_position",
        "description": (
            "执行模拟交易：开仓（action=open）、平仓（action=close）、查看持仓（action=list）。"
            "当用户明确表达要买入/卖出/开仓/平仓某个资产时——尤其是给出了数量、止损、止盈等参数"
            "（例如「帮我买入1股NVDA，设8%止损20%止盈」）——必须调用本工具执行 action=open，"
            "用户的明确指示本身就是确认，不要只做分析。"
            "这是唯一能实际建仓/平仓的工具；generate_signal 只做信号分析、不会建立任何持仓。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "close", "list"],
                    "description": "操作类型",
                },
                "symbol": {"type": "string", "description": "资产代码（open/close 时必填）"},
                "direction": {
                    "type": "string",
                    "enum": ["long", "short"],
                    "description": "方向，默认 long",
                },
                "quantity": {"type": "number", "description": "数量，默认 1"},
                "stop_loss_pct": {
                    "type": "number",
                    "description": "止损百分比，如 8 表示 -8% 止损",
                },
                "take_profit_pct": {
                    "type": "number",
                    "description": "止盈百分比，如 20 表示 +20% 止盈",
                },
            },
            "required": ["action"],
        },
    },
]
