import { PageHeader } from "../../_components/PageHeader";
import { CompanyImportWorkspace } from "./_components/CompanyImportWorkspace";

export default function CompanyImportPage() {
  return (
    <div>
      <PageHeader
        eyebrow="企业拍照录入"
        eyebrowEn="Company Photo Intake"
        title="拍照新增企业"
        titleEn="Add Company by Photo"
        description="上传企业名片、宣传册、目录封面或企业资料截图，生成可人工复核的企业草稿，确认后再写入正式企业库。"
        descriptionEn="Upload business cards, brochures, catalog covers, or company screenshots to generate a reviewable company draft before saving it to the company catalog."
      />
      <CompanyImportWorkspace />
    </div>
  );
}
