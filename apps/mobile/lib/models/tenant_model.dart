/// A tenant (shop/branch) the signed-in account can act as. Written fresh
/// for Raje3 — generalized shape (id/name/isActive), not the reference
/// project's individual-vs-business split, which was specific to their
/// product.
class TenantModel {
  final String id;
  final String name;
  final bool isActive;

  const TenantModel({
    required this.id,
    required this.name,
    this.isActive = false,
  });

  factory TenantModel.fromJson(Map<String, dynamic> json) {
    return TenantModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      isActive: json['is_active'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'is_active': isActive,
      };
}
