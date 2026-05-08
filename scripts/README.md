# 构建脚本

此目录包含 Hermes Agent for iStoreOS 的所有构建和打包脚本。

## 脚本说明

| 脚本 | 说明 | 输出 |
|------|------|------|
| `build.sh` | 完整构建（验证 + 打包） | `dist/luci-app-hermes.tar.gz`, `dist/hermes-istoreos-full-src.tar.gz` |
| `build-ipk.sh` | .ipk 包构建 | `dist/luci-app-hermes_2.0.0_all.ipk` |
| `build-ipk.py` | .ipk 包构建（Python 版，纯代码实现） | `dist/luci-app-hermes_2.0.0_all.ipk` |

## 使用方法

```bash
# 完整构建
bash scripts/build.sh

# 构建 .ipk
bash scripts/build-ipk.sh
# 或
python3 scripts/build-ipk.py
```

## 构建产物

所有构建输出在 `dist/` 目录（不在 Git 版本控制中）：

- `luci-app-hermes.tar.gz` — iStoreOS 离线安装包
- `hermes-istoreos-full-src.tar.gz` — 完整源码包
- `luci-app-hermes_2.0.0_all.ipk` — opkg 标准安装包
