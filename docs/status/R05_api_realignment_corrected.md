# R05 API 状态纠正、任务重排与安全修正

- 任务编号与名称：R05 API 状态纠正、任务重排与安全修正
- 负责线程：R05 项目计划纠正与安全修正 Agent
- 开始时间：2026-05-27T19:53:35+08:00
- 完成时间：2026-05-27T19:59:29+08:00
- 状态：done

## 完成内容

- 修正 API 数据源优先级：
  - P0：Bailian、World Bank、GDELT、YouTube、Etsy、CSV fallback。
  - P1：UN Comtrade no-key-first，可选环境变量增强，不阻塞 MVP。
  - P2：eBay、Rakuten、Reddit future providers。
- 将 `docs/TASK_BOARD.md` 从旧 T00-T22 调整为 T00-T04 done + R05-R25 后续任务。
- 在 `agent.md` 增加 2026-05-27 API 状态纠正记录。
- 新增 `docs/API_CAPABILITY_MATRIX.md`。
- 更新 `docs/SECURITY.md`，补充敏感文件、前端限制、配置状态接口和 no-key-first 策略。
- 更新 `.gitignore`，确保本地敏感文件名和 `secrets/` 不会被 Git 跟踪。

## 修改路径

- `.gitignore`
- `agent.md`
- `docs/API_SOURCES.md`
- `docs/API_CAPABILITY_MATRIX.md`
- `docs/SECURITY.md`
- `docs/TASK_BOARD.md`
- `docs/status/R05_api_realignment_corrected.md`

## 安全扫描结果

- 未读取、复制或输出 `cross_border_api_keys_and_docs.txt` 内容。
- `git check-ignore` 已确认敏感文件名和 `secrets/` 路径会被忽略。
- 已对已跟踪文件和未忽略新增文件执行脱敏扫描，未发现高置信度真实 Key、Secret、Token、Cookie 或私钥块。
- 仅允许环境变量名、空值和明显占位符出现在文档中。

## 验证命令与结果

```powershell
git check-ignore -v cross_border_api_keys_and_docs.txt cross_border_api_env_template.txt secrets/foo.txt
```

结果：通过，三个路径均被 `.gitignore` 规则覆盖。

```powershell
cd backend
py -3.11 -m pytest tests
```

结果：通过，`25 passed`。

```powershell
cd frontend
npm run lint
```

结果：通过，无 ESLint warnings/errors。

```powershell
cd frontend
npm run build
```

结果：通过，Next.js 生产构建成功。

## 环境变量影响

- 未新增真实环境变量值。
- 文档中明确后续任务使用的变量名：
  `DASHSCOPE_API_KEY`、`BAILIAN_API_KEY`、`YOUTUBE_DATA_API_KEY`、`ETSY_KEYSTRING`、`ETSY_SHARED_SECRET`、`UN_COMTRADE_API_KEY`、`EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`、`RAKUTEN_APP_ID`、`RAKUTEN_APPLICATION_ID`、`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`。

## Blockers

- 无。

## Follow-up

- R07 需要实现配置状态接口，只返回 configured/not_configured/public/optional 等状态。
- R08 需要先建立统一 provider 抽象，R09-R12 再并行接入 P0 数据源。
- R13 的 UN Comtrade 必须保持非阻塞增强。
- R22-R24 不应影响 MVP 主流程。
