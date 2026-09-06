/**
 * المنصّة والفريق — القسم 5 بالشريط. يجمع الشاشات المصقولة يدوياً (9.1/9.2): الإعدادات الحيّة
 * والأسرار. فريق الإدارة وسجل التدقيق يُبنيان بخطوة تالية من نفس المرحلة، لا هنا بعد.
 *
 * «مفاتيح المزوّدين» ليست نفس «الأسرار» — انظر AdminProviderSecrets.tsx's own header. قدرتان
 * مختلفتان (platform.secrets مقابل platform.secrets_manage)، فمن يملك واحدة فقط يرى تبويباً واحداً
 * يعمل والثاني يرفض — هذا مقصود، لا خطأ بالواجهة.
 */
import { Segmented } from '../rj-ui/Segmented';
import { useState } from 'react';
import { AdminAuditLog } from './AdminAuditLog';
import { AdminConfig } from './AdminConfig';
import { AdminSecrets } from './AdminSecrets';
import { AdminProviderSecrets } from './AdminProviderSecrets';
import { AdminLegal } from './AdminLegal';
import { AdminDisputeReports } from './AdminDisputeReports';
import { AdminWhatsAppTemplates } from './AdminWhatsAppTemplates';
import { AdminTeam } from './AdminTeam';
import { AdminCompliance } from './AdminCompliance';
import type { AdminSession } from './api';

type SubTab = 'config' | 'secrets' | 'provider_secrets' | 'wa_templates' | 'legal' | 'disputes' | 'team' | 'audit' | 'compliance';

export function AdminPlatform({ session, initialSub, initialOpenProvider }: {
  session: AdminSession;
  /** رابط تحويل مباشر من شاشة ثانية (مثل تبويب "بوابة الدفع" بالمالية) — يفتح على هذا التبويب
   *  الفرعي مباشرة بدل "الإعدادات الحيّة" الافتراضي. */
  initialSub?: SubTab;
  initialOpenProvider?: string;
}) {
  const [sub, setSub] = useState<SubTab>(initialSub ?? 'config');
  return (
    <div className="flex flex-col gap-4">
      <div className="px-6 pt-6">
        <Segmented
          value={sub}
          onChange={(v) => setSub(v as SubTab)}
          options={[
            { value: 'config', label: 'الإعدادات الحيّة' },
            { value: 'secrets', label: 'الأسرار' },
            { value: 'provider_secrets', label: 'مفاتيح المزوّدين' },
            { value: 'wa_templates', label: 'قوالب واتساب' },
            { value: 'legal', label: 'المستندات القانونية' },
            { value: 'disputes', label: 'تقارير الدفاع النزاعي' },
            { value: 'team', label: 'فريق الإدارة' },
            { value: 'audit', label: 'سجل التدقيق' },
            { value: 'compliance', label: 'الامتثال' },
          ]}
        />
      </div>
      {sub === 'config' ? <AdminConfig session={session} /> : null}
      {sub === 'secrets' ? <AdminSecrets session={session} /> : null}
      {sub === 'provider_secrets' ? (
        <AdminProviderSecrets session={session} initialOpenProvider={initialOpenProvider} />
      ) : null}
      {sub === 'wa_templates' ? <AdminWhatsAppTemplates session={session} /> : null}
      {sub === 'legal' ? <AdminLegal session={session} /> : null}
      {sub === 'disputes' ? <AdminDisputeReports session={session} /> : null}
      {sub === 'team' ? <AdminTeam session={session} /> : null}
      {sub === 'audit' ? <AdminAuditLog session={session} /> : null}
      {sub === 'compliance' ? <AdminCompliance session={session} /> : null}
    </div>
  );
}
