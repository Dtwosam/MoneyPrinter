# Authorization branch binding correction

The fresh authorization JSON binds exact report HEAD `15978c6c54eab0243db8fe07237b6ec354e532a1`.

A package-review documentation commit was accidentally added after that report commit. The review evidence must be preserved on a separate review lineage, while the authorization branch itself must point back to the exact bound report HEAD before any Mac alignment or wrapper application. No replacement authorization is created and the reviewed JSON bytes/SHA remain unchanged.
