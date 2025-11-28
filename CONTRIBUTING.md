# Contributing

欢迎贡献！请遵循以下步骤：

1. Fork 仓库并创建分支：

```
git checkout -b feature/your-feature
```

2. 安装开发依赖：

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
```

3. 本地格式化和测试：

```
pre-commit run --all-files
pytest
```

4. 提交并创建 PR。至少一位审阅者通过后合并。
