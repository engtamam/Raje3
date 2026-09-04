/**
 * المنصّة والفريق — القسم ٥ بالشريط. يجمع الشاشات المصقولة يدوياً (٩.١/٩.٢): الإعدادات الحيّة
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
import { AdminTeam } from './AdminTeam';
import type { AdminSession } from './api';

type SubTab = 'config' | 'secrets' | 'provider_secrets' | 'legal' | 'disputes' | 'team' | 'audit';

export function AdminPlatform({ session }: { session: AdminSession }) {
  const [sub, setSub] = useState<SubTab>('config');
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
            { value: 'legal', label: 'المستندات القانونية' },
            { value: 'disputes', label: 'تقارير الدفاع النزاعي' },
            { value: 'team', label: 'فريق الإدارة' },
            { value: 'audit', label: 'سجل التدقيق' },
          ]}
        />
      </div>
      {sub === 'config' ? <AdminConfig session={session} /> : null}
      {sub === 'secrets' ? <AdminSecrets session={session} /> : null}
      {sub === 'provider_secrets' ? <AdminProviderSecrets session={session} /> : null}
      {sub === 'legal' ? <AdminLegal session={session} /> : null}
      {sub === 'disputes' ? <AdminDisputeReports session={session} /> : null}
      {sub === 'team' ? <AdminTeam session={session} /> : null}
      {sub === 'audit' ? <AdminAuditLog session={session} /> : null}
    </div>
  );
}
