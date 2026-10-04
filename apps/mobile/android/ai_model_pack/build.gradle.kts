// The on-device AI model, delivered as a Play Asset Delivery install-time pack instead of a
// plain Flutter asset. See lib/core/ai/ai_config.dart's own doc comment for why the model ships
// WITH the app at all (owner's own decision, 2026-09-22) — this module is what makes that
// possible under Google Play's own base-module cap (200MB compressed), which the raw ~2.77GB
// model file blew past by an order of magnitude when it lived inside app/src/main/assets/.
//
// install-time, not on-demand or fast-follow: Play downloads this pack together with the base
// app at install time, before the user ever opens it — the closest equivalent, under Play's own
// delivery model, to "the model ships with the app, no separate download the user notices" that
// the owner's own decision already committed to. The user experiences one install, one wait, the
// model already there the first time the app opens — never a second download triggered later.
plugins {
    id("com.android.asset-pack")
}

assetPack {
    packName.set("ai_model_pack")
    dynamicDelivery {
        deliveryType.set("install-time")
    }
}
