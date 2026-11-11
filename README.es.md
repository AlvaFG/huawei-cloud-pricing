# huawei-cloud-pricing

Consultá el precio de cualquier servicio de Huawei Cloud desde la línea de comandos, en cualquier región, y guardá en Git la lista completa de servicios y especificaciones.

[Read in English](README.md)

La calculadora de precios de Huawei le pide cada número a un endpoint público. Este proyecto manda el mismo pedido, así que un script puede responder «¿cuánto cuesta esto en esa región?» sin navegar la página. También copia las listas oficiales de servicios y especificaciones de Huawei, comprueba que cada una se pueda cotizar de verdad y guarda fotos de precios con fecha, para ver cómo cambian con el tiempo.

> **No oficial.** Este proyecto no tiene relación con Huawei ni cuenta con su aval. Lee los endpoints que usa la calculadora pública, que no son una API documentada y pueden cambiar sin aviso. Los precios son de lista, en USD: sin impuestos, descuentos ni condiciones de contrato. Confirmá siempre el precio en la consola antes de comprar.

## Cobertura

Todos los números salen de `data/` y los reconstruye la herramienta, no están escritos a mano. [docs/services.md](docs/services.md) tiene la tabla de cada servicio.

- **105** servicios del menú de la calculadora, con **270** tipos de recurso y **8.612** especificaciones, copiados de las listas de Huawei.
- **226** tipos de recurso se cotizaron contra el endpoint en todas las formas de cobro que tienen. **31** no se pudieron cotizar y **5** solo en algunas formas de cobro; figuran con el motivo.
- **227** respuestas se compararon además con el precio de lista del catálogo de Huawei y coincidieron.

«Verificado» significa que una o dos especificaciones del tipo de recurso se cotizaron de verdad, no que lo estén todas. Lo que no se verificó figura en la lista, no se esconde.

## Qué incluye

- **Una línea de comandos** para encontrar un servicio, listar sus especificaciones y cotizar una en cualquier región y forma de cobro.
- **Todos los servicios que lista Huawei** en `data/services.json` y **todas sus especificaciones** en `data/specs/<servicio>.json`.
- **Un registro de verificación** (`data/verification.json`) de lo que respondió y con qué pedido, y una **página de cobertura** que lo muestra.
- **Fotos de precios con fecha** (`data/snapshots/`) de productos de referencia en varias regiones. El historial de Git de esa carpeta es el historial de precios.
- **Comandos `verify` y `audit`** que avisan cuando los endpoints o los datos dejan de funcionar.
- **Acciones de GitHub** que actualizan la foto cada semana y redescubren los servicios cada mes, y abren un pull request con lo que cambió.
- **Una skill para agentes** (`.claude/skills/huawei-cloud-pricing/`) para que un agente de IA cotice y actualice los datos siguiendo instrucciones escritas.

Python 3.9 o superior. No hay nada que instalar.

## Primeros pasos

```bash
git clone https://github.com/AlvaFG/huawei-cloud-pricing.git
cd huawei-cloud-pricing

python3 -m hwprice services --search nat          # buscar un servicio
python3 -m hwprice specs --service nat            # sus especificaciones y formas de cobro

# Un NAT Gateway por un mes en LA-Santiago
python3 -m hwprice quote --region la-south-2 --service nat --spec natgateway_small

# Un servidor, pago por uso durante un mes (730 horas)
python3 -m hwprice quote --region la-south-2 --service ecs --spec s6.large.4.linux --billing ondemand

# Un disco de 100 GB
python3 -m hwprice quote --region la-south-2 --service evs --spec GPSSD --size 100
```

```
57.30 USD  (nat natgateway_small, la-south-2, monthly)
43.80 USD  (ecs s6.large.4.linux, la-south-2, ondemand)
for 730 unit(s) of Duration (unit id 4)
9.40 USD  (evs GPSSD, la-south-2, monthly)
```

Si una región no ofrece un producto, lo informa en lugar de inventar un precio. Si un código coincide con más de una especificación, las lista en lugar de elegir.

## ¿El precio depende de la región?

Sí. El endpoint es el mismo para todas las regiones: la región es un campo del pedido (`regionId`). El precio del mismo producto cambia con ella, y algunos productos no se ofrecen en todas. Ver [docs/regions-and-prices.md](docs/regions-and-prices.md).

## Comandos

| Comando | Qué hace |
|---|---|
| `services` | Lista los servicios y cuántos tipos de recurso están verificados |
| `specs` | Lista las especificaciones de un servicio, con sus formas de cobro |
| `quote` | Cotiza una especificación en una región: mensual, anual o pago por uso |
| `verify` | Comprueba que los endpoints y los datos sigan funcionando. El código de salida 1 indica que algo se rompió |
| `audit` | Repite todos los pedidos verificados e informa fallos y cambios de precio |
| `refresh` | Cotiza los productos de referencia en cada región, guarda una foto e imprime qué cambió |
| `discover` | Reconstruye servicios, especificaciones y verificación desde las listas de Huawei (unos 30 minutos) |
| `docs` | Regenera la página de cobertura |

## Límites que conviene conocer

- **La lista de especificaciones es la de la región por defecto.** Una región puede vender una especificación que la lista no tiene (RDS for PostgreSQL `medium.2` se vende en LA-Santiago pero no figura). `quote --unlisted --resource-type <tipo>` la envía tal como se escribe.
- **El pago por uso cotiza un consumo.** Un servidor se cotiza por horas, otros servicios por GB, llamadas o una cantidad. `quote` imprime qué unidad usó y `--usage` cambia el monto. Una especificación que se cobra por varios factores necesita `--usage-factor`.
- **Algunos tipos de recurso no se pueden cotizar por la calculadora.** Figuran en [docs/services.md](docs/services.md) con el motivo.

## Mantenerlo al día

Hay tres formas, de menos a más automática. Detalle en [docs/updating.md](docs/updating.md).

1. **A mano:** `python3 -m hwprice verify && python3 -m hwprice audit && python3 -m hwprice refresh`, y commitear.
2. **Con un agente de IA:** apuntalo a este repositorio y pedile que actualice los precios. La skill le dice qué comandos correr, cómo leer el resultado y cómo arreglar lo que falla.
3. **Automático:** [`refresh.yml`](.github/workflows/refresh.yml) corre cada lunes y [`discover.yml`](.github/workflows/discover.yml) el primer día de cada mes. Activá *Allow GitHub Actions to create and approve pull requests* en la configuración del repositorio.

## Cómo funciona

```
hwprice/client.py    arma el pedido y lee la respuesta (solo biblioteca estándar, 4 pedidos por segundo como máximo)
hwprice/discover.py  lee las listas de servicios y especificaciones de Huawei y comprueba que cada una se cotice
hwprice/specs.py     encuentra una especificación y arma su línea de pedido
hwprice/snapshot.py  cotiza los productos de referencia en varias regiones y compara dos fotos
hwprice/report.py    escribe la página de cobertura
hwprice/cli.py       los comandos de arriba
data/                servicios, especificaciones, verificación, productos de referencia, regiones y fotos
docs/                endpoints, formato de pedidos, regiones, cómo encontrar códigos, cómo actualizar, cobertura
```

## Sé un cliente educado

El endpoint sirve una página web pública. Este cliente espera al menos 250 ms entre pedidos y se identifica en el `User-Agent`. Mantené eso, no lo uses en bucles apretados y leé los términos de Huawei del sitio que consultás.

## Contribuir

Se aceptan pull requests que arreglen un tipo de recurso, agreguen regiones o productos de referencia, o mejoren la documentación. Ver [CONTRIBUTING.md](CONTRIBUTING.md). No incluyas nunca credenciales, IDs de cuenta ni datos privados.

## Licencia

[MIT](LICENSE)
