# iStoreOS 商店集成

此目录包含 iStoreOS 商店所需的元数据文件。

## 文件说明

- `store.json` — iStoreOS 商店插件元数据（名称、版本、描述、截图等）

## 发布流程

1. 更新 `store.json` 中的版本号和 changelog
2. 构建 .ipk 包: `bash scripts/build-ipk.sh`
3. 将 .ipk 上传到 GitHub Releases
4. 更新 iStoreOS 商店源
