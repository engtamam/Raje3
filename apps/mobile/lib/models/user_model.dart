/// The signed-in account. Written fresh for Raje3 — generic shape only
/// (id/phone/name/email), no reference-project fields (their model carried
/// hair-analysis-specific profile data that doesn't apply here).
class UserModel {
  final String id;
  final String phone;
  final String? fullName;
  final String? email;

  const UserModel({
    required this.id,
    required this.phone,
    this.fullName,
    this.email,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      fullName: json['full_name'] as String?,
      email: json['email'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'phone': phone,
        if (fullName != null) 'full_name': fullName,
        if (email != null) 'email': email,
      };
}
