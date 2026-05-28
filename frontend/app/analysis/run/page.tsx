import { PageHeader } from "../../_components/PageHeader";
import { AnalysisRunWorkspace } from "./_components/AnalysisRunWorkspace";

export default function RunAnalysisPage() {
  return (
    <div>
      <PageHeader
        eyebrow="智能体协作 / Agent Workflow"
        title="运行分析 / Run Analysis"
        description="选择企业、产品和目标国家，启动后端多智能体工作流，并实时展示企业画像、产品理解、数据采集、竞品分析、机会评分、营销准备与报告准备过程。"
      />
      <AnalysisRunWorkspace />
    </div>
  );
}
