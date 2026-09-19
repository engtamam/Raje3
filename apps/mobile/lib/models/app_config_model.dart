/// Server-driven runtime config, fetched by [AppConfigService]. Written
/// fresh for Raje3, minimal — just the region block AppConstants actually
/// consumes today (see AppConstants.loadRegionConfig). The reference
/// project's equivalent model also carried enum-label lookups and DPIA
/// thresholds specific to its own product; none of that is ported.
class AppConfigModel {
  final RegionConfig region;

  const AppConfigModel({required this.region});

  factory AppConfigModel.fromJson(Map<String, dynamic> json) {
    return AppConfigModel(
      region: RegionConfig.fromJson(
        json['region'] as Map<String, dynamic>? ?? const {},
      ),
    );
  }
}

class RegionConfig {
  final String currency;
  final String currencySymbol;
  final num taxRate;

  const RegionConfig({
    this.currency = 'SAR',
    this.currencySymbol = 'ر.س',
    this.taxRate = 15,
  });

  factory RegionConfig.fromJson(Map<String, dynamic> json) {
    return RegionConfig(
      currency: json['currency'] as String? ?? 'SAR',
      currencySymbol: json['currency_symbol'] as String? ?? 'ر.س',
      taxRate: json['tax_rate'] as num? ?? 15,
    );
  }
}
