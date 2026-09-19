/// The signed-in account. Written fresh for Raje3 — generic shape only
/// (id/phone/name), no reference-project fields (their model carried
/// hair-analysis-specific profile data that doesn't apply here).
///
/// NO EMAIL FIELD, ON PURPOSE. Raje3's real identity door
/// (services/operations/app/api/v1/signup.py, core/signup.py) is phone-only
/// end to end — opening a shop takes phone + password + shop name, signing
/// back in takes phone + password. Neither door has ever taken or returned
/// an email address; a field here that nothing populates is exactly the kind
/// of drift that later looks like a real capability.
///
/// `id`/`fullName` ARE BUILT LOCALLY, NOT PARSED FROM A SERVER RESPONSE.
/// `/api/v1/signup/signin` mints only `{access_token, refresh_token, tenant}`
/// — there is no user-profile object anywhere in this flow, so [id] holds the
/// tenant id (the one identifier the door actually gives back) and
/// [fullName] holds the shop name only at the moment of signup, when the
/// caller typed it.
class UserModel {
  final String id;
  final String phone;
  final String? fullName;

  const UserModel({
    required this.id,
    required this.phone,
    this.fullName,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      fullName: json['full_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'phone': phone,
        if (fullName != null) 'full_name': fullName,
      };
}
