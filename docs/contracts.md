# Контракт анализа и визуализации, версия 1.1

Этот файл фиксирует интерфейс между `rules.json`, независимым Python-анализатором и автономным HTML. Изменения контракта согласует интегратор. Физические допущения и источники — в [model.md](model.md).

## Конфигурация и математика

Используются точные ключи `rules.json`; идентификаторы профилей `metric`, `feet_reference`, режимов `nominal`, `bounded_stress`. Варианты `base`, `threat_3000`, `threat_10000`, `target_3000`, `target_10000`. Полное произведение — 20 запусков. Порядок следует массивам конфигурации.

Версия 1.1 заменяет цилиндр цели сферой: `zones.target.shape="sphere"`, `center_alt_m=0`, `target_motion="static_xyz"`. Высота центра — конечное число в метрах; значение 0 является согласованным допущением сценария. XY остаются в `scenario.target`. Конфигурация версии 1.0 и прежняя цилиндрическая семантика отклоняются; старые отчёты и HTML нужно пересоздать.

Состояния заданы в SI относительно t=0; `p(t)=p0+v*t`, интервал `[0,duration_s]`. Для каждого самолёта и дрона ошибки `eh(t)=ph+vh*t`, `ez(t)=pz+vz*t` берутся из выбранного `mode.error_bounds`. Цель точна. Новых измерений нет.

* Пара: `dh < H+eh_i+eh_j AND abs(dz) < V+ez_i+ez_j` одновременно.
* Цель: `d3 < target_radius+eh_i+ez_i`, где расстояние считается до `(x_target,y_target,center_alt_m)`. Цель точная; её ошибки не добавляются. Радиус в base/stress равен `5120+1.1*t` м, в base/nominal — 5000 м.
* Дрон: `d3 < threat_radius+eh_i+ez_i+eh_drone+ez_drone`. Для обеих сфер сумма горизонтальной и вертикальной границ — консервативная верхняя граница нормы 3D ошибки. Stress-событие не доказывает реализовавшееся нарушение.
* Высота: `z-ez < alt_min OR z+ez > alt_max`; исходные границы из `scenario.airspace`. Равенство допустимо.
* Ограничения скорости в stress проверяются на всём допустимом диапазоне постоянной скорости: горизонтальный модуль `[max(0,speed-evh),speed+evh]`, вертикальная компонента `[vz-evz,vz+evz]`. Тангенциальное ускорение, вертикальное ускорение и скорость поворота каждого допустимого baseline равны нулю. Предел поворота определяется креном и скоростью; предел тангенциального ускорения не является ограничением бокового ускорения.

Физические неравенства строгие, их границы не расширяются numerical epsilon. Численная точность используется для вычисления корней/невязок; ровно касательное сближение не создаёт событие. Связные интервалы нарушения объединяются только если их объединение действительно связно с учётом открытых концов. Отдельный безопасный момент не удаляется объединением.

## Python API

Пакет `airspace`, модуль `airspace.analysis`:

```python
load_inputs(scenario_path) -> (scenario: dict, flights: list[dict])
load_rules(rules_path) -> dict
analyze_all(scenario: dict, flights: list[dict], rules: dict) -> dict
write_reports(analysis: dict, output_dir) -> None
```

CLI: `python3 tools/analyze_baseline.py --scenario scenario.json --rules rules.json --output-dir reports` (эти значения — defaults относительно корня проекта). Stdlib, Python >=3.9. Не импортировать генератор HTML. Проверять конечность чисел, уникальность ID и допустимость/поддерживаемость конфигурации; положительные задержки и иная модель неопределённости не должны молча игнорироваться.

`write_reports` создаёт `analysis.json`, `events.csv`, `summary.csv`, `sensitivity.csv` и краткую `summary.md`. Числа в JSON сохраняются без преждевременного округления, NaN/Infinity запрещены. Выход детерминированный, без изменяющегося timestamp. CSV содержит profile/mode/variant/run ID. Сумма длительностей событий может включать пересечения и не называется длительностью небезопасного полёта.

## Корневой JSON и HTML payload

```javascript
DATA = {duration_s, scenario, flights, rules, analysis};
analysis = {
  schema_version: "1.1", duration_s: 1200,
  runs: [/* Run */],
  // Дополнительная provenance/sensitivity/limitations metadata разрешена.
};
```

HTML читает готовые интервалы из `analysis.runs`. Он не вычисляет конфликты заново. Формулы положения, отображаемых расстояний и размеров зон допустимы для визуализации. Готовый HTML содержит всю конфигурацию и все отчёты и работает через file:// без сети. Пример payload — `tests/fixtures/analysis_example.json`, явно синтетический и заменяемый реальными результатами при интеграции.

На карте обе зоны показаны сечениями на высоте выбранного самолёта: `sqrt(R_eff²−(z−z_center)²)` при `abs(z−z_center)<R_eff`; иначе сечение отсутствует. Карточка самолёта показывает 3D-расстояние до цели и отдельно горизонтальное расстояние.

## Run

```javascript
{
  id: "metric__nominal__base",
  profile_id: "metric", mode_id: "nominal", variant_id: "base",
  thresholds: {
    horizontal_m: 9260, vertical_m: 300,
    threat_radius_m: 5000, target_radius_m: 5000, target_alt_m: 0,
    alt_min_m: 3000, alt_max_m: 12000
  },
  events: [/* Event */],
  summary: {
    event_count: 0, aircraft_pair_count: 0,
    affected_flight_count: 0, affected_flight_ids: [],
    initial_event_count: 0,
    counts_by_type: {aircraft_aircraft: 0, aircraft_threat: 0,
      aircraft_target: 0, altitude: 0, motion: 0},
    first_event_s: null,
    total_event_duration_s: 0
  },
  initial_state: {has_violations: false, event_ids: []},
  motion_checks: {all_pass: true, scope: "constant_velocity_baseline",
    checks: [/* flight_id, rule_id, units, observed_min, observed_max,
                allowed_min, allowed_max, passes */]}
}
```

`aircraft_pair_count` — число уникальных неупорядоченных пар только типа aircraft_aircraft, а не количество всех событий. `affected_flight_ids` учитывает все типы событий, не включает THREAT/TARGET. Каждое motion-нарушение также создаёт Event, чтобы его можно было показать в UI; отсутствующая нижняя/верхняя граница в motion-check обозначается null.

## Event

```javascript
{
  id: "metric__nominal__base__aircraft_aircraft__F018__F034__0",
  type: "aircraft_aircraft", rule_id: "aircraft_separation",
  participants: ["F018", "F034"], flight_ids: ["F018", "F034"],
  profile_id: "metric", mode_id: "nominal", variant_id: "base",
  start_s: 10, end_s: 14,
  start_inclusive: false, end_inclusive: false,
  initial_violation: false, continues_at_horizon: false,
  severity: "nominal_violation",
  representative_s: 12,
  duration_s: 4,
  thresholds: {
    horizontal: {intercept_m: 1000, slope_mps: 0},
    vertical: {intercept_m: 300, slope_mps: 0}
  },
  metrics: {
    horizontal_min: {value_m: 0, time_s: 12, attained: true},
    vertical_min: {value_m: 0, time_s: 12, attained: true},
    distance_3d_min: {value_m: 0, time_s: 12, attained: true}
  }
}
```

Выше числа — иллюстрация синтетического случая, не реальный F018/F034. Типы: aircraft_aircraft, aircraft_threat, aircraft_target, altitude, motion. `participants` специальных объектов использует `THREAT`, `TARGET`; для altitude/motion — только самолёт. `rule_id` различает нижнюю/верхнюю высотную границу и отдельные ограничения движения.

В событии используются только релевантные thresholds/metrics: пары — horizontal и vertical, обе сферы — radius, высота — alt_min_m/alt_max_m и error_vertical (аффинная), motion — имена лимитов и наблюдаемый диапазон. У цели `rule_id="target_sphere"`, метрики horizontal_min, vertical_min и distance_3d_min считаются относительно её центра. Высота центра записана в `run.thresholds.target_alt_m` и сводных CSV. Для altitude метрика altitude_min/altitude_max того же вида; для motion допустимо пустое metrics, т.к. результаты находятся в motion_checks и thresholds. Дополнительные диагностические поля разрешены. UI не должен предполагать наличие всех метрик.

Все расстояния в metrics — расстояния **номинальных центров**, минимизированные отдельно на замыкании интервала события. `attained` указывает, достигается ли минимум внутри самого интервала; если нет, значение является инфимумом. Минимумы разных компонент могут достигаться в разные моменты и не служат совместным доказательством конфликта. `representative_s` — точка внутри интервала (для UI перехода), обычно середина, а не обязательно время CPA.

Stress-события имеют severity=possible_violation, даже если часть интервала также содержит номинальное нарушение. Для отображения подтверждённого номинального нарушения UI может сопоставить **готовые интервалы** соответствующего nominal run. Это не повторная геометрическая детекция. Номинальные и stress события не складываются как независимые события одного режима.

Интервал всегда обрезан `[0,duration_s]`; inclusivity вычисляется по истинному условию нарушения в концах. Если нарушение продолжается на t=1200, end_inclusive=true и continues_at_horizon=true. Equality-safe корень не включается. Начальное нарушение имеет start=0, start_inclusive=true, initial_violation=true. UI сравнивает время с сохранёнными концами/флагами без физических допусков.

## Проверяемые примеры

`tests/fixtures/detection_examples.json` содержит отдельные математические примеры входа и ожидаемых интервалов: вход/выход, касание, равенство по высоте, постоянный конфликт, обрезка горизонтом, несовпадение горизонтального и вертикального интервалов. Это независимые простые ожидания, не снимок вывода основного детектора.

Ожидание для реальных данных при base/nominal: 3 aircraft-пары в metric и 24 в feet_reference; у этих пар нет исходного нарушения. Это контроль вычислений, не критерий подгонки правил. Полный отчёт также учитывает угрозу, цель, высоту и динамику.

Пример сферы: цель `(0,0,0)`, R=5000, самолёт `(-6000,0,3000)` со скоростью `(200,0,0)`, T=60. Ожидаемый интервал цели — `(10,50)` с, минимум 3D=3000 м при t=30. При высоте 5000 м та же траектория лишь касается сферы и не создаёт события; при 8100 м проходит выше неё. Для неподвижного самолёта `(0,0,5100)` и только вертикальной ошибки `20+0.1*t` stress-интервал на T=1200 — `(800,1200]`.
