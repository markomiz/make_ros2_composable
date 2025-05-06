import os
import re
from pathlib import Path

def find_ros2_node_constructors(root_dir: str):
    constructor_pattern = re.compile(
        r'(\w+)::\1\s*\([^)]*\)\s*:\s*(?:public\s+)?(?:Node|LifecycleNode)\b'
        r'|'
        r'(\w+)::\2\s*\([^)]*\)\s*:\s*\1\s*\('
    )

    matches = []

    for path in Path(root_dir).rglob('*.cpp'):
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue

        for match in constructor_pattern.finditer(content):
            class_name = match.group(1) or match.group(2)
            matches.append((class_name, str(path)))

    return matches

def confirm_nodes(nodes):
    confirmed = []

    for class_name, path in nodes:
        while True:
            choice = input(f"Make node '{class_name}' in {path} composable? [y/n]: ").strip().lower()
            if choice == 'y':
                confirmed.append((class_name, path))
                break
            elif choice == 'n':
                break
            else:
                print("Please enter 'y' or 'n'.")

    return confirmed

def find_enclosing_namespace(content: str, class_name: str) -> str:
    """
    Tracks brace depth and namespace blocks to determine the fully-qualified namespace
    for a given class constructor.
    """
    lines = content.splitlines()
    namespace_stack = []
    brace_depth = 0
    depth_to_ns = {}

    # Get constructor line number
    constructor_line_num = None
    for idx, line in enumerate(lines):
        if re.search(rf'\b{class_name}::{class_name}\s*\(', line):
            constructor_line_num = idx
            break
    if constructor_line_num is None:
        return ""

    # Walk from top to constructor line, tracking brace depth
    for i in range(constructor_line_num + 1):
        line = lines[i].strip()

        # Match `namespace name` (brace may come later)
        ns_match = re.match(r'namespace\s+(\w+)', line)
        if ns_match:
            pending_namespace = ns_match.group(1)
            # We expect a `{` to follow — might be on the same or later line
            for j in range(i, constructor_line_num + 1):
                if '{' in lines[j]:
                    depth_to_ns[brace_depth] = pending_namespace
                    namespace_stack.append(pending_namespace)
                    brace_depth += lines[j].count('{') - lines[j].count('}')
                    break
            continue

        brace_depth += line.count('{') - line.count('}')
        # If we reduced brace depth and exited a namespace
        if brace_depth < len(namespace_stack):
            namespace_stack = namespace_stack[:brace_depth]

    return "::".join(namespace_stack) + ("::" if namespace_stack else "")


def update_main_constructors(class_name: str, cpp_path: str):
    cpp_file = Path(cpp_path)
    package_dir = cpp_file.parent.parent
    main_candidates = list(package_dir.rglob("main*.cpp")) + [cpp_file]

    constructor_call_pattern = re.compile(
        rf'std::make_shared<([\w:]*{class_name})>\s*\(\s*\)'
    )

    for path in main_candidates:
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue

        if constructor_call_pattern.search(content):
            updated = constructor_call_pattern.sub(
                r'std::make_shared<\1>(rclcpp::NodeOptions{})', content
            )
            path.write_text(updated, encoding='utf-8')
            print(f"🔧 Updated constructor call in: {path}")

def update_node_constructor(class_name: str, file_path: str):
    try:
        content = Path(file_path).read_text(encoding='utf-8')
    except UnicodeDecodeError:
        print(f"⚠️  Skipping non-UTF8 file: {file_path}")
        return

    if f"{class_name}::" in content and "NodeOptions" in content:
        print(f"✔️  Skipping {class_name}: already uses NodeOptions.")
        return

    constructor_regex = re.compile(
        rf'({class_name}::{class_name}\s*\([^)]*\))(\s*:\s*[^{{]+)'
    )

    match = constructor_regex.search(content)
    if not match:
        print(f"❌ Constructor for {class_name} not found in {file_path}")
        return

    new_signature = f"{class_name}::{class_name}(const rclcpp::NodeOptions & options)"
    old_initializer = match.group(2)
    updated_initializer = re.sub(r'\bNode\s*\(([^)]*)\)', r'Node(\1, options)', old_initializer)
    updated_constructor = f"{new_signature}{updated_initializer}"
    updated_content = constructor_regex.sub(updated_constructor, content, count=1)

    namespace_prefix = find_enclosing_namespace(content, class_name)
    register_macro = f"RCLCPP_COMPONENTS_REGISTER_NODE({namespace_prefix}{class_name})"
    if register_macro not in updated_content:
        updated_content += f"\n\n#include \"rclcpp_components/register_node_macro.hpp\"\n{register_macro}\n"

    Path(file_path).write_text(updated_content, encoding='utf-8')
    print(f"✅ Updated: {class_name} in {file_path}")

    update_main_constructors(class_name, file_path)

def update_header_constructor_declaration(class_name: str, cpp_path: str):
    cpp_file = Path(cpp_path)
    cpp_stem = cpp_file.stem
    src_dir = cpp_file.parent
    package_dir = src_dir.parent
    include_dir = package_dir / "include"

    candidate_headers = []
    candidate_headers += list(src_dir.glob(f"{cpp_stem}.h*"))

    if include_dir.exists():
        candidate_headers += list(include_dir.glob(f"{cpp_stem}.h*"))
        nested_include_dir = include_dir / package_dir.name
        if nested_include_dir.exists():
            candidate_headers += list(nested_include_dir.glob(f"{cpp_stem}.h*"))

    if not candidate_headers:
        print(f"⚠️  Header for {class_name} not found near {cpp_path}")
        return

    header_path = candidate_headers[0]

    try:
        content = header_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        print(f"⚠️  Skipping non-UTF8 header: {header_path}")
        return

    declaration_regex = re.compile(rf'\b{class_name}\s*\([^;{{]*\);')
    match = declaration_regex.search(content)
    if not match:
        print(f"⚠️  Constructor declaration for {class_name} not found in {header_path}")
        return

    new_declaration = f'  explicit {class_name}(const rclcpp::NodeOptions & options);'
    updated_content = declaration_regex.sub(new_declaration, content, count=1)

    header_path.write_text(updated_content, encoding='utf-8')
    print(f"📝 Header updated: {header_path}")

def apply_composable_conversion(confirmed_nodes):
    for class_name, path in confirmed_nodes:
        update_node_constructor(class_name, path)
        update_header_constructor_declaration(class_name, path)

if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print("Usage: python make_composable.py <path_to_ros2_workspace>")
        sys.exit(1)

    root = sys.argv[1]
    nodes = find_ros2_node_constructors(root)

    if not nodes:
        print("No ROS 2 node constructors found.")
        sys.exit(0)

    print(f"\nFound {len(nodes)} ROS 2 node constructors.")
    confirmed = confirm_nodes(nodes)

    if not confirmed:
        print("\nNo nodes selected for composable conversion.")
    else:
        print("\nNodes marked for conversion:")
        for class_name, path in confirmed:
            print(f"  - {class_name} in {path}")

        apply_composable_conversion(confirmed)
