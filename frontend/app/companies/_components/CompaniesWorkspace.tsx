"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { LoadingState } from "../../_components/LoadingState";
import {
  Company,
  CompanyPayload,
  createCompany,
  deleteCompany,
  getFriendlyErrorMessage,
  listCompanies,
  updateCompany,
} from "../../_lib/api-client";

type CompanyFormState = {
  name: string;
  region: string;
  industry: string;
  description: string;
  target_countries: string;
};

const emptyForm: CompanyFormState = {
  name: "",
  region: "",
  industry: "",
  description: "",
  target_countries: "",
};

export function CompaniesWorkspace() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<CompanyFormState>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === selectedId) ?? null,
    [companies, selectedId],
  );

  useEffect(() => {
    void refreshCompanies();
  }, []);

  async function refreshCompanies() {
    setLoading(true);
    setError(null);
    try {
      const response = await listCompanies();
      setCompanies(response.items);
      setSelectedId((current) => {
        if (current && response.items.some((company) => company.id === current)) {
          return current;
        }
        return response.items[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  function startCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setNotice(null);
  }

  function startEdit(company: Company) {
    setEditingId(company.id);
    setSelectedId(company.id);
    setNotice(null);
    setForm({
      name: company.name,
      region: company.region ?? "",
      industry: company.industry ?? "",
      description: company.description ?? "",
      target_countries: company.target_countries?.join(", ") ?? "",
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const payload = toCompanyPayload(form);
      const saved = editingId
        ? await updateCompany(editingId, payload)
        : await createCompany(payload);
      setCompanies((current) => {
        if (editingId) {
          return current.map((company) => (company.id === saved.id ? saved : company));
        }
        return [saved, ...current];
      });
      setSelectedId(saved.id);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(editingId ? "企业信息已更新。" : "企业已创建。");
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(company: Company) {
    const confirmed = window.confirm(`确认删除企业“${company.name}”？关联产品会一并删除。`);
    if (!confirmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await deleteCompany(company.id);
      setCompanies((current) => current.filter((item) => item.id !== company.id));
      setSelectedId((current) => (current === company.id ? null : current));
      if (editingId === company.id) {
        startCreate();
      }
      setNotice("企业已删除。");
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink">{editingId ? "编辑企业" : "新增企业"}</h2>
          {editingId ? (
            <button className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700" onClick={startCreate} type="button">
              新增
            </button>
          ) : null}
        </div>
        <form className="mt-5 grid gap-4" onSubmit={handleSubmit}>
          <TextInput label="企业名称" required value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
          <TextInput label="所在地区" value={form.region} onChange={(value) => setForm({ ...form, region: value })} />
          <TextInput label="行业/产业带" value={form.industry} onChange={(value) => setForm({ ...form, industry: value })} />
          <TextInput label="目标国家" placeholder="US, JP, GB" value={form.target_countries} onChange={(value) => setForm({ ...form, target_countries: value })} />
          <label className="grid gap-2">
            <span className="text-sm font-medium text-slate-700">企业简介</span>
            <textarea
              className="min-h-24 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </label>
          <button
            className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={submitting || !form.name.trim()}
            type="submit"
          >
            {submitting ? "保存中" : editingId ? "保存修改" : "创建企业"}
          </button>
        </form>
        {notice ? <p className="mt-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink">企业列表</h2>
          <button className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700" onClick={() => void refreshCompanies()} type="button">
            刷新
          </button>
        </div>
        <div className="mt-5">
          {loading ? (
            <LoadingState label="正在加载企业" />
          ) : companies.length === 0 ? (
            <EmptyState title="暂无企业" description="创建企业后即可关联产品和导入样本。需要后端服务可用。" />
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">企业</th>
                    <th className="px-4 py-3 font-semibold">行业</th>
                    <th className="px-4 py-3 font-semibold">目标国家</th>
                    <th className="px-4 py-3 font-semibold">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {companies.map((company) => (
                    <tr key={company.id} className={selectedId === company.id ? "bg-river/5" : undefined}>
                      <td className="px-4 py-3 font-medium text-ink">{company.name}</td>
                      <td className="px-4 py-3 text-slate-600">{company.industry ?? "-"}</td>
                      <td className="px-4 py-3 text-slate-600">{company.target_countries?.join(", ") ?? "-"}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <button className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700" onClick={() => setSelectedId(company.id)} type="button">
                            详情
                          </button>
                          <button className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-river" onClick={() => startEdit(company)} type="button">
                            编辑
                          </button>
                          <button className="rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700" onClick={() => void handleDelete(company)} type="button">
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {selectedCompany ? (
          <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-base font-semibold text-ink">{selectedCompany.name}</h3>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
              <DetailItem label="地区" value={selectedCompany.region} />
              <DetailItem label="行业" value={selectedCompany.industry} />
              <DetailItem label="目标国家" value={selectedCompany.target_countries?.join(", ")} />
              <DetailItem label="更新时间" value={formatDate(selectedCompany.updated_at)} />
            </dl>
            {selectedCompany.description ? <p className="mt-3 text-sm leading-6 text-slate-600">{selectedCompany.description}</p> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  placeholder,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
        placeholder={placeholder}
        required={required}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-700">{value || "-"}</dd>
    </div>
  );
}

function toCompanyPayload(form: CompanyFormState): CompanyPayload {
  return {
    name: form.name.trim(),
    region: optionalText(form.region),
    industry: optionalText(form.industry),
    description: optionalText(form.description),
    target_countries: splitCountries(form.target_countries),
  };
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function splitCountries(value: string): string[] | null {
  const countries = value
    .split(",")
    .map((country) => country.trim())
    .filter(Boolean);
  return countries.length > 0 ? countries : null;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
