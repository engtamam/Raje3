/**
 * المنصّة والفريق — القسم ٥ بالشريط. يجمع الشاشات المصقولة يدوياً (٩.١/٩.٢): الإعدادات الحيّة
 * والأسرار. فريق الإدارة وسجل التدقيق يُبنيان بخطوة تالية من نفس المرحلة، لا هنا بعد.
 */
import { Segmented } from '../rj-ui/Segmented';
import { useState } from 'react';
import { AdminAuditLog } from './AdminAuditLog';
import { AdminConfig } from './AdminConfig';
import { AdminSecrets } from './AdminSecrets';
import { AdminTeam } from './AdminTeam';
import type { AdminSession } from './api';

type SubTab = 'config' | 'secrets' | 'team' | 'audit';

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
            { value: 'team', label: 'فريق الإدارة' },
            { value: 'audit', label: 'سجل التدقيق' },
          ]}
        />
      </div>
      {sub === 'config' ? <AdminConfig session={session} /> : null}
      {sub === 'secrets' ? <AdminSecrets session={session} /> : null}
      {sub === 'team' ? <AdminTeam session={session} /> : null}
      {sub === 'audit' ? <AdminAuditLog session={session} /> : null}
    </div>
  );
}
