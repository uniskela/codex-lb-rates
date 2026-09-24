# Changelog

## [0.8.0](https://github.com/uniskela/codex-lb-rates/compare/v0.7.0...v0.8.0) (2026-09-24)


### Features

* add Lovelace card visual config editor ([39a931e](https://github.com/uniskela/codex-lb-rates/commit/39a931e97bc9f4bb2b726131227a6ac7f2c3353a))
* add Lovelace card visual config editor ([2dd273b](https://github.com/uniskela/codex-lb-rates/commit/2dd273b3056b00cf02328af4b406ab2cf3de7e7e))


### Bug Fixes

* tighten visual editor assertConfig for object entities ([2ce8688](https://github.com/uniskela/codex-lb-rates/commit/2ce8688d4994c617bd087f8200321de2cb3aa889))

## [0.7.0](https://github.com/uniskela/codex-lb-rates/compare/v0.6.4...v0.7.0) (2026-09-24)


### Features

* add 429 cooldown UX for LB polling ([73adc7d](https://github.com/uniskela/codex-lb-rates/commit/73adc7d05dcb2e2b89abd18f742a8e0c41ce287f))
* add 429 cooldown UX for LB polling ([62a93fc](https://github.com/uniskela/codex-lb-rates/commit/62a93fc01926e5f47cebe03eb46000e264a99a28)), closes [#2](https://github.com/uniskela/codex-lb-rates/issues/2)
* add Lovelace card for pool remaining ([6b972b7](https://github.com/uniskela/codex-lb-rates/commit/6b972b76f5918c0837dfe58a7f2e3b07baba58da))
* add Lovelace card for pool remaining ([13189b4](https://github.com/uniskela/codex-lb-rates/commit/13189b4a9b4467e8cd977263418191c231b9be76)), closes [#2](https://github.com/uniskela/codex-lb-rates/issues/2)
* add optional used percent sensors ([b0b0ab5](https://github.com/uniskela/codex-lb-rates/commit/b0b0ab5451bb884a68e2aaeadd7bb3a57ab36791))
* add optional used percent sensors ([1ca33ea](https://github.com/uniskela/codex-lb-rates/commit/1ca33ea1e54205e1f8b9e56dc948c20c70dc271b)), closes [#2](https://github.com/uniskela/codex-lb-rates/issues/2)
* expose requestUsage and additional quotas ([18f1200](https://github.com/uniskela/codex-lb-rates/commit/18f1200929542ed8caec4ef66b1c07c59e6f8c93))
* expose requestUsage and additional quotas ([8e278d5](https://github.com/uniskela/codex-lb-rates/commit/8e278d5ceef273670b878ac73f073f14538a11b1)), closes [#2](https://github.com/uniskela/codex-lb-rates/issues/2)


### Bug Fixes

* derive used % from remaining when missing ([ccd3e6b](https://github.com/uniskela/codex-lb-rates/commit/ccd3e6bafc085be4b690b9c2bbdda6734993e985))
* prefer canonical spark quota and keep reset-only windows ([63e4397](https://github.com/uniskela/codex-lb-rates/commit/63e43977d725f70603b41437ca604668fedfccca))
* preserve 429 cooldown across entry updates ([795bcaf](https://github.com/uniskela/codex-lb-rates/commit/795bcafc7443f922b023441e6b4af814ae4848fe))
* repair Lovelace resource types during registration ([8848d2f](https://github.com/uniskela/codex-lb-rates/commit/8848d2fdb07c10ef6ba3fc63c975bb623a76f458))
* retain polling cooldown across coordinator reloads ([269c499](https://github.com/uniskela/codex-lb-rates/commit/269c4992f594e38f56e1b0d6d6906d1b1a1d6bff))
* satisfy hassfest for Lovelace card setup ([e57ad3a](https://github.com/uniskela/codex-lb-rates/commit/e57ad3a4a65620516840cea30510e3bfa88ac64c))

## [0.6.4](https://github.com/uniskela/codex-lb-rates/compare/v0.6.3...v0.6.4) (2026-09-23)


### Bug Fixes

* publish expanded docs on Latest via 0.6.4 ([256f53e](https://github.com/uniskela/codex-lb-rates/commit/256f53e1e8526211af75c5d472c151208fa84889))

## [0.6.3](https://github.com/uniskela/codex-lb-rates/compare/v0.6.2...v0.6.3) (2026-09-16)


### Bug Fixes

* expose poll freshness and reset timing diagnostics ([ec99e75](https://github.com/uniskela/codex-lb-rates/commit/ec99e7518f8beb9cde9b12b2f83cd81661dd4954))
* expose quota timing in diagnostics ([df7393d](https://github.com/uniskela/codex-lb-rates/commit/df7393d496c45bf001635a8463da815ac74b8715))
* track successful provider poll freshness ([f0bcf1a](https://github.com/uniskela/codex-lb-rates/commit/f0bcf1a8527f5db8cef3a79830fb6f7ae276c7ad))

## [0.6.2](https://github.com/uniskela/codex-lb-rates/compare/v0.6.1...v0.6.2) (2026-09-16)


### Bug Fixes

* label quota windows from reported duration ([fe8d080](https://github.com/uniskela/codex-lb-rates/commit/fe8d080143675d08d2f5da2d34f353bedc99dcfd))
* label quota windows from reported duration ([a3468dc](https://github.com/uniskela/codex-lb-rates/commit/a3468dcb95e422a9fe8eee6b3db24ef637cd0973))
* preserve legacy labels without window metadata ([4a759e4](https://github.com/uniskela/codex-lb-rates/commit/4a759e4062f491028288991ca27165dd32d6256c))

## [0.6.1](https://github.com/uniskela/codex-lb-rates/compare/v0.6.0...v0.6.1) (2026-09-16)


### Bug Fixes

* make quota alerts event-driven and version blueprint ([b6b8d21](https://github.com/uniskela/codex-lb-rates/commit/b6b8d21d7246e90f1f414002b327c0119767c492))
* make quota blueprint event driven ([f107bda](https://github.com/uniskela/codex-lb-rates/commit/f107bda16764d63d21dd026efa345fb50a2d98b9))
* recheck quota alerts after automation reload ([4b04be5](https://github.com/uniskela/codex-lb-rates/commit/4b04be51b868c3470f1a691bf4a4da4562e63067))

## [0.6.0](https://github.com/uniskela/codex-lb-rates/compare/v0.5.0...v0.6.0) (2026-09-15)


### Features

* add reset display toggle for countdown vs absolute ([f8f3d3d](https://github.com/uniskela/codex-lb-rates/commit/f8f3d3dc9bf39cbd17b79760fa91a178b0a4e3c8))


### Bug Fixes

* improve weighted quota sensors ([6083f1a](https://github.com/uniskela/codex-lb-rates/commit/6083f1adaa68aa4703ff366f5c2bb13a94a67f68))
* preserve disabled/hidden entities when windows drop ([3be848a](https://github.com/uniskela/codex-lb-rates/commit/3be848aee1362a77e0a39b1dfb9b6bf3b8ae28d2))
* reconcile quota windows and render account status ([1c6b9e2](https://github.com/uniskela/codex-lb-rates/commit/1c6b9e2e4a00770f58b43b77e8c079649b512526))

## [0.5.0](https://github.com/uniskela/codex-lb-rates/compare/v0.4.2...v0.5.0) (2026-09-11)


### Features

* multi-sensor multi-threshold quota alert blueprint ([6ffa16c](https://github.com/uniskela/codex-lb-rates/commit/6ffa16c5cd5df1f856905888ee2c45fcecb0f89b))
* multi-sensor multi-threshold quota alert blueprint ([412176f](https://github.com/uniskela/codex-lb-rates/commit/412176f300f753cc69c37182c76a3d4e7161a7f2))

## [0.4.2](https://github.com/uniskela/codex-lb-rates/compare/v0.4.1...v0.4.2) (2026-09-11)


### Bug Fixes

* use notify services instead of templated device actions ([b68efc6](https://github.com/uniskela/codex-lb-rates/commit/b68efc625663c10410698413159966d4d6c2f460))
* use notify services instead of templated device actions ([1b3896e](https://github.com/uniskela/codex-lb-rates/commit/1b3896e768f2f2d9640a79d1fddb96e1f27a9092))

## [0.4.1](https://github.com/uniskela/codex-lb-rates/compare/v0.4.0...v0.4.1) (2026-09-11)


### Bug Fixes

* make quota blueprint helper required and style notifies ([0005d75](https://github.com/uniskela/codex-lb-rates/commit/0005d75d6f9735629ed79241a4571a92069ddcc4))
* make quota blueprint helper required and style notifies ([7b61e52](https://github.com/uniskela/codex-lb-rates/commit/7b61e52585586b4708adca2f72ab1fefe444219e))

## [0.4.0](https://github.com/uniskela/codex-lb-rates/compare/v0.3.2...v0.4.0) (2026-09-11)


### Features

* add persistent and phone notify to quota blueprint ([0e46148](https://github.com/uniskela/codex-lb-rates/commit/0e461481a0db2ff6febb0c479f9f005f4e6e7689))
* add persistent and phone notify to quota blueprint ([31c3d8d](https://github.com/uniskela/codex-lb-rates/commit/31c3d8d8a413895dbe65d2979d6480bd1240878f))

## [0.3.2](https://github.com/uniskela/codex-lb-rates/compare/v0.3.1...v0.3.2) (2026-09-10)


### Bug Fixes

* brand icons + hide empty monthly (v0.3.2) ([a069652](https://github.com/uniskela/codex-lb-rates/commit/a069652a78c47d48a60ffe264db2b68ba3d22736))
* complete brand assets and hide empty monthly sensors ([4483754](https://github.com/uniskela/codex-lb-rates/commit/4483754b4c7669e90a46b92ddcbd7e48d648e096))

## [0.3.1](https://github.com/uniskela/codex-lb-rates/compare/v0.3.0...v0.3.1) (2026-09-10)


### Features

* add Release Please for automated versioning and GitHub releases ([37fcda0](https://github.com/uniskela/codex-lb-rates/commit/37fcda0afa7889e0462de96a7df0b5cf871cd45d))
