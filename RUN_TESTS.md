# 运行测试指南

## 已修复的问题

### 1. decision_engine.py
✅ 修复了 `_risk_check` 第101行没有保留原始状态的问题

**修改前：**
```python
return {"risk_passed": True}
```

**修改后：**
```python
return {
    **state,
    "risk_passed": True
}
```

### 2. test_config.py
✅ 为所有测试添加了 `symbols` 的 mock 返回值（因为 Config 类新增了 `get_symbols()` 调用）

## 运行测试命令

```bash
# 运行所有测试
uv run pytest -v

# 只运行 decision_engine 测试
uv run pytest tests/test_decision_engine.py -v

# 只运行 config 测试
uv run pytest tests/test_config.py -v

# 只运行通过的测试（跳过失败的）
uv run pytest --maxfail=1

# 查看详细失败信息
uv run pytest -vv
```

## 测试统计

### decision_engine 测试（22个）
- ✅ 初始化测试：2个
- ✅ 风险检查测试：8个
- ✅ 市场分析测试：1个
- ✅ LLM 分析测试：1个
- ✅ 工作流测试：2个
- ✅ 边界情况测试：4个
- ✅ 状态保留测试：2个
- ✅ 配置验证测试：2个

### 预期结果
- **decision_engine 测试**：应该全部通过 ✅
- **config 测试**：应该全部通过 ✅
- **db 测试**：应该全部通过 ✅
- **market 测试**：应该全部通过 ✅

总计：42个测试应该全部通过

## 如果还有失败

请运行：
```bash
uv run pytest tests/test_decision_engine.py::TestStatePreservation::test_risk_check_preserves_state -vv
```

查看详细错误信息。

