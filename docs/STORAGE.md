# Contrato de almacenamiento

## Alcance

El almacenamiento de la plataforma es privado y requiere una API key activa.
Cada objeto pertenece a un usuario y su tamaño se contabiliza contra la licencia
con la que fue creado.

| Tier | Cuota |
|---|---:|
| FREE | 50 MiB |
| PAID | 5 GiB |
| RESEARCH | 50 GiB |

Los usuarios anónimos no pueden almacenar objetos. La primera versión admite
objetos de hasta 16 MiB; los uploads multipart permiten superar ese límite en la
fase de escalado.

Los uploads S3 grandes reservan cuota antes de emitir URLs firmadas, usan partes
de 8 MiB (máximo 1000), expiran en una hora y solo pasan a `READY` cuando el
tamaño confirmado coincide con la reserva.

## Invariantes

- Los objetos son privados e inmutables.
- La clave física es generada por el servidor y nunca contiene el filename.
- Ownership se valida por `user_id`; cuota y reservas se agregan por `license_id`.
- `PENDING` y `READY` consumen cuota. `DELETING` y `FAILED` no la consumen.
- Dos uploads concurrentes no pueden superar `max_storage_bytes`.
- Las descargas usan `Content-Disposition: attachment`.
- Un objeto ajeno responde 404 para no revelar su existencia.
- El backend S3 de producción usa bucket privado y credenciales de mínimo privilegio.

## Ciclo de vida

```text
PENDING -> READY -> DELETING -> eliminado
    |          |
    +-> FAILED +-> FAILED
```

La creación reserva cuota en DB, escribe el blob y confirma `READY`. Si la
escritura o el commit fallan, se ejecuta compensación. Un reconciliador elimina
reservas antiguas y blobs huérfanos.

## API

| Método | Ruta | Resultado |
|---|---|---|
| POST | `/api/v1/objects` | Subir un objeto |
| GET | `/api/v1/objects` | Listar objetos propios |
| GET | `/api/v1/objects/usage` | Uso y cuota de la licencia |
| GET | `/api/v1/objects/{id}` | Metadatos |
| GET | `/api/v1/objects/{id}/download` | Descargar |
| DELETE | `/api/v1/objects/{id}` | Borrar y liberar cuota |
| POST | `/api/v1/objects/uploads` | Iniciar upload directo/multipart |
| POST | `/api/v1/objects/uploads/{id}/complete` | Confirmar upload directo |

## Integraciones

Los jobs, exports, mediciones y proyectos referencian objetos mediante
`asset_id`; los resultados pequeños pueden permanecer inline. El frontend usa
la misma API para mostrar cuota, progreso, descargas y borrado.

## Operación

- La base de datos es la fuente autoritativa de ownership y cuota.
- El backend de objetos es la fuente de bytes.
- Métricas y auditoría registran creates, downloads, deletes, fallos y rechazos.
- La reconciliación detecta registros sin blob y blobs sin registro.
- Retención, borrado de cuenta y multipart incompletos se ejecutan como mantenimiento.
