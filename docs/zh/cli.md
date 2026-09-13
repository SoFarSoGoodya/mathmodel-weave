# 命令参考

使用项目环境，并通过 `--help` 查看当前确切参数：

```text
uv run mmagent --help
uv run mmagent init CASE_DIR
uv run mmagent doctor CASE_DIR
uv run mmagent serve CASE_DIR
```

通常流程是：初始化、导入并校正证据、提交协调任务或命令、运行并轮询、准备和执行实验、冻结证据、构建论文、不可变暂存、人工批准，最后导出。Case 路径相对于 case 根目录；不支持的字段会明确失败，凭据不能写入 JSON 或 TOML。

`docs/modules/` 下的模块说明包含契约和 Python 入口。

