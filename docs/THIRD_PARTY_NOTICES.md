# Third-Party Notices

本项目的部分文档设计方法借鉴了 OpenAI `role-specific-plugins` 仓库，但未复制、安装或接入该仓库中的插件实现、connector 绑定、MCP 配置、assets、scripts、templates、品牌素材或 workspace 配置。

## OpenAI role-specific-plugins

- Source: https://github.com/openai/role-specific-plugins
- License: MIT
- Copyright: Copyright (c) 2026 OpenAI

借鉴范围仅限文档层面的工作流方法，例如角色化任务拆分、来源验证、证据记录、草稿/审阅/确认、报告 QA、source posture 和 UX 审查。任何复制或实质性改编的文档片段均受上游 MIT License 约束。

## Connector and Workspace Binding Exclusions

本项目不包含上游 `.app.json` 文件，不复制 connector app id、workspace-specific connector id、OAuth/client id、MCP credentials、local workspace bindings 或任何外部 workspace 的连接配置。

未来如需示例 connector 配置，只能使用占位符，例如 `REPLACE_WITH_<CONNECTOR>_APP_OR_CONNECTOR_ID`。真实 workspace id 必须由目标部署环境单独配置，不得从上游仓库、其他 workspace 或本地凭据文件复制。

## MIT License Notice

MIT License

Copyright (c) 2026 OpenAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

