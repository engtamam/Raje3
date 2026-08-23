/** نفس صدق `../affiliates/AffiliateNav.tsx`'s own `ComingSoon` — قسم قيد البناء يقول ذلك
 *  بصراحة، لا شاشة فارغة ولا محتوى مزيّف. */
export function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <p className="text-lg">{label}</p>
      <p className="text-sm text-text-secondary">هذا القسم قيد البناء — قريبًا.</p>
    </div>
  );
}
