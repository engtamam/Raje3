<!-- Rendered by deploy/seed/legal/render_markdown.py — do not hand-edit. -->

<!-- Source of truth: this file's own values: + platform's PDPL pack (read-only). -->



## العربية


# تقييم الأثر لحماية البيانات الشخصية

*تقييم الأثر — نظام حماية البيانات الشخصية، المملكة العربية السعودية*


- **جهة التحكم**: راجِع (اسم مؤقت — يُستبدل قبل الإطلاق)
- **مسؤول حماية البيانات**: mang.raje3@gmail.com
- **الأساس النظامي لهذه الوثيقة**: اللائحة التنفيذية، المادة 25
- **متى يلزم**: قبل المعالجة عالية الخطورة (انظر قائمة التحقق)
- **الإصدار / تاريخ النفاذ**: 1.0  ·  1446-01-01 (تاريخ مؤقت)

تقييم الأثر هو تقييم مكتوب لمخاطر الخصوصية الناتجة عن نشاط معالجة، يُجرى قبل بدء النشاط، بحيث تُكتشف المخاطر وتُقلَّل مبكراً. وبموجب المادة (25) من اللائحة التنفيذية، تُجري راجِع (اسم مؤقت — يُستبدل قبل الإطلاق) تقييم أثر للحالات عالية الخطورة أدناه. وهذه الوثيقة هي المنهجية ونموذج قابل لإعادة الاستخدام: استكمل تقييماً واحداً لكل نشاط عالي الخطورة.

## متى يلزم تقييم الأثر؟ — قائمة تحقق

| ✓ | المُحفّز | ✓ | المُحفّز |
| --- | --- | --- | --- |
| ☐ | معالجة البيانات الحساسة | ☐ | ربط مجموعتين أو أكثر من مصادر مختلفة |
| ☐ | معالجة واسعة النطاق ومتكررة لبيانات ناقصي الأهلية أو عديميها | ☐ | معالجة تتطلب بطبيعتها مراقبة مستمرة لأصحاب البيانات |
| ☐ | معالجة تعتمد على تقنيات حديثة الاستخدام | ☐ | اتخاذ قرارات بناءً على المعالجة الآلية للبيانات الشخصية |
| ☐ | تقديم منتج أو خدمة تنطوي معالجتها على احتمال إلحاق ضرر جسيم بخصوصية أصحاب البيانات | ☐ | [أضف حالة أخرى لديك] |


> **لم يتحقق أي مُحفّز؟**
> - إذا لم ينطبق أي بند، فلا يلزم تقييم أثر كامل — لكن سجّل أنك فحصت النشاط ووجدته منخفض الخطورة. وعند الشك، أجرِ التقييم.

## ما يجب أن يتضمنه تقييم الأثر

يجب أن يتضمن كل تقييم أثر، كحد أدنى (اللائحة م.25-2):

| # | العنصر المطلوب |
| --- | --- |
| 1 | غرض المعالجة وأساسها النظامي. |
| 2 | طبيعة المعالجة وأنواع البيانات ومصادرها والمستقبِلون. |
| 3 | نطاق المعالجة ونطاقها الجغرافي. |
| 4 | سياق المعالجة والعلاقات ذات الصلة. |
| 5 | الضرورة والتناسب وتقليل البيانات. |
| 6 | شدة الأثر على أصحاب البيانات واحتماله. |
| 7 | تدابير منع المخاطر أو الحد منها ومدى ملاءمتها. |


## نموذج تقييم الأثر — قالب فارغ

- **اسم النشاط / المرجع**: [ACTIVITY]
- **المالك / المُقيّم**: [OWNER]
- **الغرض والأساس النظامي**: [PURPOSE + LEGAL_BASIS]
- **طبيعة البيانات وأنواعها ومصادرها والمستقبِلون**: [DATA_DETAILS]
- **النطاق والنطاق الجغرافي**: [SCOPE]
- **السياق والعلاقات**: [CONTEXT]
- **الضرورة والتناسب وتقليل البيانات**: [NECESSITY]
- **تاريخ التقييم / المراجعة التالية**: [DATE]

| الخطر على الأفراد | الاحتمال | الشدة | إجراء الحد | المتبقي |
| --- | --- | --- | --- | --- |
| [الخطر 1] | [م/و/ع] | [م/و/ع] | [الإجراء] | [م/و/ع] |
| [الخطر 2] | [م/و/ع] | [م/و/ع] | [الإجراء] | [م/و/ع] |
| [الخطر 3] | [م/و/ع] | [م/و/ع] | [الإجراء] | [م/و/ع] |


## مثال مُستكمل — تقييم أثر مكتمل

- **النشاط**: الدخول بالتعرف على الوجه — BIO-01
- **الغرض والأساس النظامي**: دخول أسرع وأكثر أماناً؛ الأساس: الموافقة الصريحة
- **البيانات والمصادر والمستقبِلون**: قالب بصمة الوجه؛ من المستخدمين؛ يُشارك مع مزود المصادقة فقط
- **النطاق والجغرافيا**: نحو 50,000 مستخدم؛ تُعالَج وتُخزَّن داخل المملكة
- **الضرورة وتقليل البيانات**: ميزة اختيارية؛ يبقى الدخول بكلمة المرور متاحاً؛ يُخزَّن القالب لا الصور الخام

| الخطر على الأفراد | الاحتمال | الشدة | إجراء الحد | المتبقي |
| --- | --- | --- | --- | --- |
| سرقة/انتحال البيانات الحيوية | منخفض | مرتفع | التشفير، فحص الحيوية، التخزين داخل المملكة | منخفض |
| الاستخدام لغير غرض الدخول | منخفض | متوسط | تقييد الغرض، ضبط الوصول، سجلات التدقيق | منخفض |


## النتيجة، نسخة المعالج، وإعادة التقييم

- **** القرار: ☐ المتابعة  ☐ المتابعة مع تطبيق إجراءات الحد أعلاه  ☐ عدم المتابعة.
- **** نُسلّم نسخة من هذا التقييم إلى كل جهة معالجة تعمل نيابةً عنا في المعالجة التي يتناولها. (اللائحة م.25-3)
- **** ومتى أظهر هذا التقييم أن المعالجة ستُلحق ضرراً بخصوصية أصحاب البيانات الشخصية، فلا نمضي فيها استناداً إلى التقييم وحده، بل نعالج أسباب ذلك الضرر، ونُعيد إجراء تقييم الأثر على المعالجة بعد تعديلها. (اللائحة م.25-4)
- **** ونُعيد هذا التقييم كلما تغيّر النشاط أو البيانات التي يعالجها أو المخاطر التي ينطوي عليها تغيّراً جوهرياً — فتقييم الأثر يصف نشاط المعالجة كما هو، لا كما كان عند إطلاقه.

- أجراه (مسؤول حماية البيانات): ________________________
- اعتمده: ________________________

## مطابقة ضوابط النظام

| الضابط | المادة | الدليل في |
| --- | --- | --- |
| لزوم تقييم الأثر للمعالجة عالية الخطورة | اللائحة م.25-1 | البند 1 |
| الحد الأدنى لمحتويات التقييم | اللائحة م.25-2 | البنود 2–4 |
| نسخة للمعالج؛ إعادة التقييم عند الضرر المحتمل | اللائحة م.25-3، 25-4 | البند 5 |


### المصادر الرسمية
- اللائحة التنفيذية لنظام حماية البيانات، المادة 25 — sdaia.gov.sa
- نظام حماية البيانات الشخصية (م/19)، المادة 22 — sdaia.gov.sa



---


## English


# Data Protection Impact Assessment

*DPIA — Personal Data Protection Law (PDPL), Kingdom of Saudi Arabia*


- **Controller**: راجِع (اسم مؤقت — يُستبدل قبل الإطلاق)
- **Data Protection Officer**: mang.raje3@gmail.com
- **Legal basis for this document**: Implementing Regulation, Art. 25
- **When required**: Before high-risk processing (see the checklist)
- **Version / Effective date**: 1.0  ·  1446-01-01 (تاريخ مؤقت)

A DPIA is a written assessment of the privacy risks of a processing activity, carried out BEFORE the activity begins, so risks are found and reduced early. Under Article 25 of the Implementing Regulation, راجِع (اسم مؤقت — يُستبدل قبل الإطلاق) conducts a DPIA for the high-risk cases below. This document is the method and a reusable form: complete one DPIA per high-risk activity.

## When Is a DPIA Required? — Trigger Checklist

| ✓ | Trigger | ✓ | Trigger |
| --- | --- | --- | --- |
| ☐ | Processing sensitive data | ☐ | Linking 2+ datasets from different sources |
| ☐ | Large-scale AND repetitive processing of the data of persons with partial or no legal capacity | ☐ | Processing that by its nature requires constant monitoring of Data Subjects |
| ☐ | Processing based on newly adopted technologies | ☐ | Making decisions based on automated processing of Personal Data |
| ☐ | Providing a product or service whose processing is likely to cause serious harm to Data Subjects' privacy | ☐ | [ADD YOUR OWN TRIGGER] |


> **No trigger ticked?**
> - If none apply, a full DPIA is not mandatory — but record that you screened the activity and found it low-risk. When in doubt, do the DPIA.

## What the DPIA Must Contain

Each DPIA must include, at a minimum (Reg. Art. 25-2):

| # | Required element |
| --- | --- |
| 1 | Purpose of the processing and its legal basis. |
| 2 | Nature and types of data, its sources, and the recipients. |
| 3 | Scope of processing and its geographic scope. |
| 4 | Context of the processing and the relationships involved. |
| 5 | Necessity, proportionality, and data minimization. |
| 6 | Severity and likelihood of the impact on data subjects. |
| 7 | Measures to prevent or mitigate the risks, and their suitability. |


## DPIA Form — Blank Template

- **Activity name / reference**: [ACTIVITY]
- **Owner / assessor**: [OWNER]
- **Purpose & legal basis**: [PURPOSE + LEGAL_BASIS]
- **Nature, types, sources & recipients**: [DATA_DETAILS]
- **Scope & geographic scope**: [SCOPE]
- **Context & relationships**: [CONTEXT]
- **Necessity, proportionality & minimization**: [NECESSITY]
- **Date assessed / next review**: [DATE]

| Risk to individuals | Likelihood | Severity | Mitigation measure | Residual |
| --- | --- | --- | --- | --- |
| [RISK 1] | [L/M/H] | [L/M/H] | [MITIGATION] | [L/M/H] |
| [RISK 2] | [L/M/H] | [L/M/H] | [MITIGATION] | [L/M/H] |
| [RISK 3] | [L/M/H] | [L/M/H] | [MITIGATION] | [L/M/H] |


## Worked Example — One Completed DPIA

- **Activity**: Face-recognition login — BIO-01
- **Purpose & legal basis**: Faster, more secure sign-in; basis: explicit consent
- **Data, sources & recipients**: Facial biometric template; from users; shared with auth provider only
- **Scope & geography**: ~50,000 app users; processed & stored in-Kingdom
- **Necessity & minimization**: Optional feature; password login still offered; template stored, not raw images

| Risk to individuals | Likelihood | Severity | Mitigation measure | Residual |
| --- | --- | --- | --- | --- |
| Biometric theft / spoofing | Low | High | Encryption, liveness check, in-Kingdom storage | Low |
| Use beyond login purpose | Low | Medium | Purpose limitation, access controls, audit logs | Low |


## Outcome, Processor Copy & Re-assessment

- **** Decision: ☐ Proceed  ☐ Proceed with the mitigations above  ☐ Do not proceed.
- **** We provide a copy of this assessment to every Processor acting on our behalf in relation to the processing it covers. (Reg. Art. 25-3)
- **** Where this assessment indicates that the processing would harm the privacy of Data Subjects, we do not proceed on the strength of the assessment alone: we address the causes of that harm, and we conduct the impact assessment again on the amended processing. (Reg. Art. 25-4)
- **** We repeat this assessment whenever the activity, the data it processes, or the risks it carries change materially — a DPIA describes a processing activity as it is, not as it was at launch.

- Assessed by (DPO): ________________________
- Approved by: ________________________

## PDPL Control Mapping

| PDPL Control | Article | Evidenced in |
| --- | --- | --- |
| DPIA required for high-risk processing | Reg. Art. 25-1 | Sections 1 |
| Minimum contents of the DPIA | Reg. Art. 25-2 | Sections 2–4 |
| Copy to Processor; re-assess on likely harm | Reg. Art. 25-3, 25-4 | Section 5 |


### Official Sources
- PDPL Implementing Regulation, Article 25 — sdaia.gov.sa
- PDPL (Royal Decree M/19), Article 22 — sdaia.gov.sa



---
