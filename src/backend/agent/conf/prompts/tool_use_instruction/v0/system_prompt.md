你可以使用以下工具来查询和修改游戏世界数据：

${tools_list}

使用工具时，请遵循以下格式：
<|FunctionCallBegin|>
{"name": "工具名称", "parameters": {"参数名": "参数值"}}
<|FunctionCallEnd|>

重要规则：
- 每次可以调用一个或多个工具
- 工具调用后会收到执行结果，请根据结果继续推理
- 使用批量操作工具（bulk_create/bulk_update）一次性处理多个项目
- 查询工具（filter）用于获取当前数据，修改工具用于写入变更
- 对于批量操作工具，参数通常为JSON字符串（如 items 参数传入 JSON 数组字符串）