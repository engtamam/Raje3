# Raje3 mobile — dev convenience wrapper around flutter/dart CLI.
# Written fresh for this project (the reference app had no root Makefile).

.PHONY: get analyze test format clean gen

get:
	flutter pub get

analyze:
	flutter analyze

test:
	flutter test

format:
	dart format lib test

clean:
	flutter clean

# Regenerate lib/l10n/app_localizations*.dart from the .arb files.
gen:
	flutter gen-l10n
