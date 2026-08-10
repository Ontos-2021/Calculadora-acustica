# Operación de almacenamiento

## Comandos

```bash
python -m api.storage_ops metrics
python -m api.storage_ops reconcile
```

El worker ejecuta reconciliación al arrancar y luego según
`ACOUSTIC_STORAGE_RECONCILE_INTERVAL_SECONDS`. Las reservas `PENDING` se
consideran antiguas según `ACOUSTIC_STORAGE_PENDING_MAX_AGE_SECONDS`.

## Producción S3

- Bucket privado, bloqueo de acceso público y cifrado por defecto.
- IAM limitado a get/put/delete/list sobre el prefijo configurado.
- Lifecycle para abortar multipart incompletos y aplicar retención.
- Versionado y backup según los requisitos del despliegue.
- Alertas sobre fallos de escritura, reconciliación, crecimiento anómalo y
  objetos pendientes antiguos.

## Métricas

`GET /api/v1/storage/metrics` requiere tier RESEARCH y devuelve objetos/bytes
por estado y categoría, además de disponibilidad del backend.
