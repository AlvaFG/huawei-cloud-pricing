# huawei-cloud-pricing

Consultá precios de Huawei Cloud desde la línea de comandos, guardá su historial fechado en Git y actualizá todo con un solo comando.

[Read in English](README.md)

La calculadora de precios de Huawei le pide cada número a un endpoint público. Este proyecto manda el mismo pedido, así que un script puede responder «¿cuánto cuesta esto en esa región?» sin navegar la página. También guarda las respuestas, para ver cómo cambian los precios con el tiempo.

> **No oficial.** Este proyecto no tiene relación con Huawei ni cuenta con su aval. Lee los endpoints que usa la calculadora pública, que no son una API documentada y pueden cambiar sin aviso. Los precios son de lista, en USD: sin impuestos, descuentos ni condiciones de contrato. Confirmá siempre el precio en la consola antes de comprar.

## Qué incluye

- **Una línea de comandos** para cotizar un producto en una región.
- **Un catálogo** de códigos de producto verificados contra el endpoint (`data/catalog.json`) y la lista de los 298 códigos de servicio y recurso que conoce la calculadora (`data/services.json`).
- **Fotos de precios con fecha** (`data/snapshots/`) de los mismos productos en varias regiones. El historial de Git de esa carpeta es el historial de precios.
- **Un comando `verify`** que avisa cuando el endpoint o el catálogo dejan de funcionar.
- **Una acción semanal de GitHub** que actualiza la foto y abre un pull request con lo que cambió.
- **Una skill para agentes** (`.claude/skills/huawei-cloud-pricing/`) para que un agente de IA cotice y actualice los datos siguiendo instrucciones escritas.

Python 3.9 o superior. No hay nada que instalar.

## Primeros pasos

```bash
git clone https://github.com/AlvaFG/huawei-cloud-pricing.git
cd huawei-cloud-pricing

# Un servidor por un mes en LA-Santiago
python3 -m hwprice quote --region la-south-2 --product ecs --spec s6.large.4

# Un disco de 100 GB
python3 -m hwprice quote --region la-south-2 --product evs --spec GPSSD --size 100

# El mismo servidor, pago por uso durante un mes (730 horas)
python3 -m hwprice quote --region la-south-2 --product ecs --spec s6.large.4 --billing ondemand
```

Si una región no ofrece un producto, lo informa en lugar de inventar un precio.

## ¿El precio depende de la región?

Sí. El endpoint es el mismo para todas las regiones: la región es un campo del pedido (`regionId`). El precio del mismo producto cambia con ella, y algunos productos no se ofrecen en todas. Comparalas en `data/snapshots/` o corré `python3 -m hwprice refresh`. Ver [docs/regions-and-prices.md](docs/regions-and-prices.md).

## Comandos

| Comando | Qué hace |
|---|---|
| `quote` | Cotiza un producto del catálogo en una región (mensual o por uso) |
| `verify` | Comprueba que los endpoints y el catálogo sigan funcionando. El código de salida 1 indica que algo se rompió |
| `refresh` | Cotiza todo el catálogo en cada región de `data/regions.json`, guarda una foto e imprime qué cambió desde la anterior |
| `services` | Regenera `data/services.json` desde el menú de la calculadora |

## Mantenerlo al día

Hay tres formas, de menos a más automática. Detalle en [docs/updating.md](docs/updating.md).

1. **A mano:** `python3 -m hwprice verify && python3 -m hwprice refresh`, y commitear la foto nueva.
2. **Con un agente de IA:** apuntalo a este repositorio y pedile que actualice los precios. La skill le dice qué comandos correr, cómo leer el resultado y cómo agregar un producto que no conoce.
3. **Automático:** [`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) corre cada lunes y abre un pull request con los cambios de precio. Activá *Allow GitHub Actions to create and approve pull requests* en la configuración del repositorio.

## Agregar un producto

El catálogo tiene los productos verificados. La calculadora conoce muchos más, y lo que suele faltar es el código de especificación. [docs/discovering-codes.md](docs/discovering-codes.md) explica cómo copiarlo desde el navegador en un minuto, y `data/catalog.json` lista lo que todavía falta (por ejemplo, el código de especificación del NAT Gateway).

## Sé un cliente educado

El endpoint sirve una página web pública. Este cliente espera al menos 250 ms entre pedidos y se identifica en el `User-Agent`. Mantené eso, no lo uses en bucles apretados y leé los términos de Huawei del sitio que consultás.

## Contribuir

Se aceptan pull requests con productos nuevos para el catálogo, regiones o documentación. Ver [CONTRIBUTING.md](CONTRIBUTING.md). No incluyas nunca credenciales, IDs de cuenta ni datos privados.

## Licencia

[MIT](LICENSE)
