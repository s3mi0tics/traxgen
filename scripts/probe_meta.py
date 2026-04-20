from pathlib import Path
from traxgen.parser import parse_course

data = Path("tests/fixtures/GDZJZA3J3T.course").read_bytes()
course = parse_course(data)

print("=== parsed full course ===")
print(f"guid:        {course.header.guid:#034x}")
print(f"version:     {course.header.version.name}")
print(f"title:       {course.meta_data.title!r}")
print(f"layers:      {len(course.layer_construction_data)}")
print(f"rails:       {len(course.rail_construction_data)}")
print(f"pillars:     {len(course.pillar_construction_data)}")
print(f"generation:  {course.generation.name}")
print(f"walls:       {len(course.wall_construction_data)}")
for i, wall in enumerate(course.wall_construction_data):
    n_bal = len(wall.balcony_construction_datas)
    n_with_cell = sum(1 for b in wall.balcony_construction_datas if b.cell_construction_data)
    print(
        f"  wall[{i}] towers=({wall.lower_stacker_tower_1_retainer_id},"
        f"{wall.lower_stacker_tower_2_retainer_id}) "
        f"balconies={n_bal} with_cells={n_with_cell}"
    )
