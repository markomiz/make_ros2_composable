# 🧹 make_composable.py — ROS 2 Node Composablizer

This script helps you **automatically refactor ROS 2 nodes** into composable components by updating:

- C++ constructor definitions
- Header declarations
- `main()` files that instantiate the node
- Adds `RCLCPP_COMPONENTS_REGISTER_NODE(...)` with correct namespace

It’s ideal for migrating standalone ROS 2 nodes into component containers for improved performance and flexibility.

---

## ✅ Features

- 🔍 Recursively detects ROS 2 node constructors in `.cpp` files
- 🤖 Prompts interactively before modifying anything
- ✍️ Rewrites constructors to use `rclcpp::NodeOptions`
- 🧠 Automatically finds and updates matching header declarations
- 🛠 Updates `main()` constructor calls
- 🗾 Appends `RCLCPP_COMPONENTS_REGISTER_NODE(...)` with full namespace resolution

---

## 📆 Usage

```bash
python make_composable.py <path_to_ros2_package_or_workspace>
```

You will be prompted for each detected node:

```
Make node 'PlannerNode' in src/my_pkg/src/planner_node.cpp composable? [y/n]:
```

If confirmed:

- The constructor is refactored to accept `const rclcpp::NodeOptions & options`
- The header file is updated accordingly
- Any instantiation in a `main()` file is updated
- `RCLCPP_COMPONENTS_REGISTER_NODE(...)` is appended with full namespace

---

## 🧠 Assumptions

- Each `.cpp` file defines only one ROS 2 node constructor
- Headers are located in:
  - The same directory as the `.cpp`, or
  - An adjacent `include/` or `include/<pkg_name>/` folder
- Node is derived from `rclcpp::Node` or `rclcpp_lifecycle::LifecycleNode`

---

## ❌ Limitations

- No backup is created (use Git or add backups manually)
- No automatic formatting (you may want to run `clang-format`)
- Does not insert missing constructor declarations if not found in header

---

## 💡 Example Before/After

### Before

```cpp
PlannerNode::PlannerNode() : Node("planner_node") { }

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<PlannerNode>());
  rclcpp::shutdown();
}
```

### After

```cpp
PlannerNode::PlannerNode(const rclcpp::NodeOptions & options)
: Node("planner_node", options) { }

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<PlannerNode>(rclcpp::NodeOptions{}));
  rclcpp::shutdown();
}

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(my_namespace::PlannerNode)
```

---

## 🔧 Next Steps

- Test your composable node inside a `ComposableNodeContainer`
- Tune QoS and intra-process communication settings if needed
- Ensure launch files are updated to use component containers

---

## 📄 License

Apache 2.0

---

## 🤝 Contributions

Improvements are welcome! Open an issue or PR if you find edge cases, bugs, or want new features.

