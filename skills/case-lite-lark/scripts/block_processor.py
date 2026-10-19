"""
Block内容处理器
用于解析和处理Block内容，提取图片、表格、图表等富文本内容
"""
from typing import Dict, Any, List, Optional, Tuple, Set
import json


class BlockProcessor:
    """Block内容处理器"""

    # Block类型枚举（参考block.md）
    # 文本类型
    BLOCK_TYPE_PAGE = 1         # 页面
    BLOCK_TYPE_TEXT = 2         # 文本
    BLOCK_TYPE_HEADING1 = 3     # 一级标题
    BLOCK_TYPE_HEADING2 = 4     # 二级标题
    BLOCK_TYPE_HEADING3 = 5     # 三级标题
    BLOCK_TYPE_HEADING4 = 6     # 四级标题
    BLOCK_TYPE_HEADING5 = 7     # 五级标题
    BLOCK_TYPE_HEADING6 = 8     # 六级标题
    BLOCK_TYPE_HEADING7 = 9     # 七级标题
    BLOCK_TYPE_HEADING8 = 10    # 八级标题
    BLOCK_TYPE_HEADING9 = 11    # 九级标题
    BLOCK_TYPE_BULLET = 12      # 无序列表
    BLOCK_TYPE_ORDERED = 13     # 有序列表
    BLOCK_TYPE_CODE = 14        # 代码块
    BLOCK_TYPE_QUOTE = 15       # 引用
    BLOCK_TYPE_TODO = 17        # 待办事项

    # 图表/多媒体类型
    BLOCK_TYPE_BITABLE = 18     # 多维表格
    BLOCK_TYPE_CALLOUT = 19     # 高亮块
    BLOCK_TYPE_CHAT_CARD = 20   # 会话卡片
    BLOCK_TYPE_DIAGRAM = 21     # 流程图/UML图
    BLOCK_TYPE_DIVIDER = 22     # 分割线
    BLOCK_TYPE_FILE = 23        # 文件
    BLOCK_TYPE_GRID = 24        # 分栏
    BLOCK_TYPE_GRID_COLUMN = 25 # 分栏列
    BLOCK_TYPE_IFRAME = 26      # 内嵌
    BLOCK_TYPE_IMAGE = 27       # 图片
    BLOCK_TYPE_ISV = 28         # 开放平台小组件
    BLOCK_TYPE_MINDNOTE = 29    # 思维笔记
    BLOCK_TYPE_SHEET = 30       # 电子表格
    BLOCK_TYPE_TABLE = 31       # 表格
    BLOCK_TYPE_TABLE_CELL = 32  # 表格单元格
    BLOCK_TYPE_VIEW = 33        # 视图
    BLOCK_TYPE_QUOTE_CONTAINER = 34  # 引用容器
    BLOCK_TYPE_TASK = 35        # 任务
    BLOCK_TYPE_OKR = 36         # OKR
    BLOCK_TYPE_OKR_OBJECTIVE = 37     # OKR目标
    BLOCK_TYPE_OKR_KEY_RESULT = 38    # OKR关键结果
    BLOCK_TYPE_OKR_PROGRESS = 39      # OKR进展
    BLOCK_TYPE_ADD_ONS = 40     # 文档小组件
    BLOCK_TYPE_JIRA_ISSUE = 41  # Jira问题
    BLOCK_TYPE_WIKI_CATALOG = 42      # Wiki目录
    BLOCK_TYPE_BOARD = 43       # 画板
    BLOCK_TYPE_UNDEFINED = 999  # 未定义

    @staticmethod
    def get_block_type_names() -> Dict[int, str]:
        """
        获取Block类型ID到名称的映射

        Returns:
            Block类型ID到中文名称的字典
        """
        return {
            1: "页面",
            2: "文本",
            3: "一级标题",
            4: "二级标题",
            5: "三级标题",
            6: "四级标题",
            7: "五级标题",
            8: "六级标题",
            9: "七级标题",
            10: "八级标题",
            11: "九级标题",
            12: "无序列表",
            13: "有序列表",
            14: "代码块",
            15: "引用",
            17: "待办事项",
            18: "多维表格",
            19: "高亮块",
            20: "会话卡片",
            21: "流程图/UML",
            22: "分割线",
            23: "文件",
            24: "分栏",
            25: "分栏列",
            26: "内嵌",
            27: "图片",
            28: "开放平台小组件",
            29: "思维笔记",
            30: "电子表格",
            31: "表格",
            32: "表格单元格",
            33: "视图",
            34: "引用容器",
            35: "任务",
            36: "OKR",
            37: "OKR目标",
            38: "OKR关键结果",
            39: "OKR进展",
            40: "文档小组件",
            41: "Jira问题",
            42: "Wiki目录",
            43: "画板",
        }

    @staticmethod
    def extract_images_from_block(block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从Block中提取图片信息

        Args:
            block: Block数据字典

        Returns:
            图片信息列表，每个元素包含token、width、height等信息
        """
        images = []
        block_type = block.get("block_type")

        if block_type == BlockProcessor.BLOCK_TYPE_IMAGE:
            image_data = block.get("image", {})
            if image_data and image_data.get("token"):
                images.append({
                    "token": image_data.get("token"),
                    "width": image_data.get("width"),
                    "height": image_data.get("height"),
                    "caption": image_data.get("caption", {}).get("content", ""),
                    "block_id": block.get("block_id")
                })

        return images

    @staticmethod
    def extract_images_from_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从多个Block中提取所有图片信息

        Args:
            blocks: Block列表

        Returns:
            所有图片信息列表
        """
        all_images = []
        for block in blocks:
            images = BlockProcessor.extract_images_from_block(block)
            all_images.extend(images)
        return all_images

    @staticmethod
    def extract_chart_from_block(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从Block中提取图表信息（流程图、多维表格、电子表格、思维导图等）

        Args:
            block: Block数据字典

        Returns:
            图表信息字典，如果不是图表类型则返回None
        """
        block_type = block.get("block_type")
        block_id = block.get("block_id", "")

        # 流程图/UML图
        if block_type == BlockProcessor.BLOCK_TYPE_DIAGRAM:
            diagram_data = block.get("diagram", {})
            diagram_type = diagram_data.get("diagram_type", 0)
            return {
                "chart_type": "diagram",
                "chart_type_name": "流程图/UML图",
                "block_id": block_id,
                "diagram_type": diagram_type,  # 1=流程图, 2=UML图
                "diagram_type_name": {1: "流程图", 2: "UML图"}.get(diagram_type, f"类型{diagram_type}")
            }

        # 多维表格
        elif block_type == BlockProcessor.BLOCK_TYPE_BITABLE:
            bitable_data = block.get("bitable", {})
            return {
                "chart_type": "bitable",
                "chart_type_name": "多维表格",
                "block_id": block_id,
                "token": bitable_data.get("token", ""),
                "view_type": bitable_data.get("view_type", "")
            }

        # 电子表格
        elif block_type == BlockProcessor.BLOCK_TYPE_SHEET:
            sheet_data = block.get("sheet", {})
            return {
                "chart_type": "sheet",
                "chart_type_name": "电子表格",
                "block_id": block_id,
                "token": sheet_data.get("token", ""),
                "row_size": sheet_data.get("row_size", 0),
                "column_size": sheet_data.get("column_size", 0)
            }

        # 思维笔记
        elif block_type == BlockProcessor.BLOCK_TYPE_MINDNOTE:
            mindnote_data = block.get("mindnote", {})
            return {
                "chart_type": "mindnote",
                "chart_type_name": "思维笔记",
                "block_id": block_id,
                "token": mindnote_data.get("token", "")
            }

        # 画板
        elif block_type == BlockProcessor.BLOCK_TYPE_BOARD:
            board_data = block.get("board", {})
            return {
                "chart_type": "board",
                "chart_type_name": "画板",
                "block_id": block_id,
                "token": board_data.get("token", "")
            }

        # 内嵌（iframe，如Figma、墨刀等）
        elif block_type == BlockProcessor.BLOCK_TYPE_IFRAME:
            iframe_data = block.get("iframe", {})
            component = iframe_data.get("component", {})
            iframe_type = component.get("iframe_type", 0)

            iframe_type_names = {
                1: "哔哩哔哩",
                2: "西瓜视频",
                3: "优酷",
                4: "Airtable",
                5: "百度地图",
                6: "高德地图",
                8: "Figma",
                9: "墨刀",
                10: "Canva",
                11: "CodePen",
                12: "飞书问卷",
                13: "金数据",
                99: "其他"
            }

            return {
                "chart_type": "iframe",
                "chart_type_name": iframe_type_names.get(iframe_type, f"内嵌类型{iframe_type}"),
                "block_id": block_id,
                "iframe_type": iframe_type,
                "url": component.get("url", "")
            }

        # 文件
        elif block_type == BlockProcessor.BLOCK_TYPE_FILE:
            file_data = block.get("file", {})
            return {
                "chart_type": "file",
                "chart_type_name": "文件",
                "block_id": block_id,
                "token": file_data.get("token", ""),
                "name": file_data.get("name", ""),
                "view_type": file_data.get("view_type", 1)  # 1=卡片视图, 2=预览视图
            }

        return None

    @staticmethod
    def extract_charts_from_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从多个Block中提取所有图表信息

        支持的图表类型：
        - 流程图/UML图 (diagram)
        - 多维表格 (bitable)
        - 电子表格 (sheet)
        - 思维笔记 (mindnote)
        - 画板 (board)
        - 内嵌内容 (iframe: Figma、墨刀等)
        - 文件 (file)

        Args:
            blocks: Block列表

        Returns:
            所有图表信息列表
        """
        all_charts = []
        for block in blocks:
            chart = BlockProcessor.extract_chart_from_block(block)
            if chart:
                all_charts.append(chart)
        return all_charts

    # ==================== 表格处理方法 ====================
    # 以下方法专门用于处理表格Block（类型31）及其单元格（类型32）
    # 遵循单一职责原则：每个方法只负责一个具体的表格处理任务

    @staticmethod
    def extract_table_info(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从表格Block中提取表格元信息（结构信息）

        职责：仅提取表格的结构化元数据，不处理单元格内容
        适用场景：需要了解表格结构但不需要具体内容时使用

        Args:
            block: Block数据字典，应为表格类型（block_type=31）

        Returns:
            表格元信息字典，包含以下字段：
            - block_id (str): 表格的唯一标识
            - row_size (int): 表格行数
            - column_size (int): 表格列数
            - header_row (bool): 是否有表头行
            - header_column (bool): 是否有表头列
            - cell_ids (List[str]): 所有单元格的block_id列表，按行优先顺序排列
            - merge_info (List[Dict]): 合并单元格信息（如有）

            如果不是表格类型或数据无效则返回None

        Example:
            >>> block = {"block_type": 31, "block_id": "xxx", "table": {...}}
            >>> info = BlockProcessor.extract_table_info(block)
            >>> print(f"表格大小: {info['row_size']}行 x {info['column_size']}列")
        """
        block_type = block.get("block_type")
        if block_type != BlockProcessor.BLOCK_TYPE_TABLE:
            return None

        table_data = block.get("table", {})
        if not table_data:
            return None

        property_data = table_data.get("property", {})
        if not property_data:
            return None

        row_size = property_data.get("row_size", 0)
        column_size = property_data.get("column_size", 0)

        if row_size == 0 or column_size == 0:
            return None

        return {
            "block_id": block.get("block_id", ""),
            "row_size": row_size,
            "column_size": column_size,
            "header_row": property_data.get("header_row", False),
            "header_column": property_data.get("header_column", False),
            "cell_ids": table_data.get("cells", []),
            "merge_info": property_data.get("merge_info", [])
        }

    @staticmethod
    def extract_table_summary(block: Dict[str, Any]) -> str:
        """
        从表格Block中提取简要文本描述

        职责：生成表格的人类可读摘要，用于文本提取和展示场景
        适用场景：需要快速了解表格概况，不需要具体内容

        Args:
            block: Block数据字典，应为表格类型（block_type=31）

        Returns:
            表格的简要描述字符串，格式如：[表格: 3行×4列]
            如果无法提取信息则返回 [表格]

        Example:
            >>> block = {"block_type": 31, "table": {"property": {"row_size": 3, "column_size": 4}}}
            >>> summary = BlockProcessor.extract_table_summary(block)
            >>> print(summary)  # 输出: [表格: 3行×4列]
        """
        table_info = BlockProcessor.extract_table_info(block)
        if table_info:
            row_size = table_info["row_size"]
            column_size = table_info["column_size"]
            return f"[表格: {row_size}行×{column_size}列]"
        return "[表格]"

    @staticmethod
    def build_cell_content_map(
        cell_blocks: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        构建单元格ID到内容的映射字典

        职责：将单元格Block列表转换为可快速查询的内容映射
        适用场景：作为表格内容提取的预处理步骤

        Args:
            cell_blocks: 单元格Block数据列表，每个元素应为表格单元格类型（block_type=32）

        Returns:
            字典，键为单元格block_id，值为提取的文本内容
            空单元格不会包含在返回结果中

        Example:
            >>> cells = [{"block_id": "cell1", "block_type": 32, ...}, ...]
            >>> content_map = BlockProcessor.build_cell_content_map(cells)
            >>> print(content_map.get("cell1", ""))
        """
        cell_content_map = {}
        for cell_block in cell_blocks:
            cell_id = cell_block.get("block_id")
            if not cell_id:
                continue
            # 提取单元格文本内容
            text_content = BlockProcessor.extract_text_from_block(cell_block)
            if text_content:
                cell_content_map[cell_id] = text_content
        return cell_content_map

    @staticmethod
    def table_to_matrix(
        block: Dict[str, Any],
        cell_content_map: Optional[Dict[str, str]] = None
    ) -> List[List[str]]:
        """
        将表格Block转换为二维字符串矩阵

        职责：将表格数据转换为标准的二维数组格式，便于后续处理
        适用场景：需要对表格数据进行自定义格式化或分析时使用

        Args:
            block: 表格Block数据，应为表格类型（block_type=31）
            cell_content_map: 单元格ID到内容的映射字典（可选）
                             如果不提供，单元格内容将为空字符串
                             可通过 build_cell_content_map() 方法生成

        Returns:
            二维字符串列表，table_matrix[row][col] 表示第row行第col列的内容
            如果表格数据无效则返回空列表

        Example:
            >>> table_block = {"block_type": 31, "table": {...}}
            >>> cell_blocks = [...]  # 单元格Block列表
            >>> content_map = BlockProcessor.build_cell_content_map(cell_blocks)
            >>> matrix = BlockProcessor.table_to_matrix(table_block, content_map)
            >>> for row in matrix:
            ...     print(row)
        """
        table_info = BlockProcessor.extract_table_info(block)
        if not table_info:
            return []

        row_size = table_info["row_size"]
        column_size = table_info["column_size"]
        cell_ids = table_info["cell_ids"]

        if cell_content_map is None:
            cell_content_map = {}

        # 构建表格矩阵
        table_matrix = []
        for i in range(row_size):
            row = []
            for j in range(column_size):
                cell_idx = i * column_size + j
                if cell_idx < len(cell_ids):
                    cell_id = cell_ids[cell_idx]
                    content = cell_content_map.get(cell_id, "")
                    row.append(content)
                else:
                    row.append("")
            table_matrix.append(row)

        return table_matrix

    @staticmethod
    def table_to_markdown(
        block: Dict[str, Any],
        cells_data: Optional[List[Dict[str, Any]]] = None,
        cell_content_map: Optional[Dict[str, str]] = None
    ) -> str:
        """
        将表格Block转换为Markdown格式

        职责：将表格数据格式化为Markdown表格语法
        适用场景：导出文档、生成报告、展示表格内容

        Args:
            block: 表格Block数据，应为表格类型（block_type=31）
            cells_data: 单元格Block数据列表（可选，已废弃，推荐使用cell_content_map）
                       如果提供，会自动构建content_map
            cell_content_map: 单元格ID到内容的映射字典（可选，优先使用）
                             可通过 build_cell_content_map() 方法生成

        Returns:
            Markdown格式的表格字符串
            如果表格数据无效则返回空字符串

        Note:
            - 如果同时提供 cells_data 和 cell_content_map，优先使用 cell_content_map
            - 管道符(|)会被自动转义为 \\|
            - 空单元格会显示为空格

        Example:
            >>> table_block = {"block_type": 31, "table": {...}}
            >>> cell_blocks = [...]
            >>> content_map = BlockProcessor.build_cell_content_map(cell_blocks)
            >>> markdown = BlockProcessor.table_to_markdown(table_block, cell_content_map=content_map)
            >>> print(markdown)
            | 列1 | 列2 | 列3 |
            | --- | --- | --- |
            | 数据1 | 数据2 | 数据3 |
        """
        # 优先使用 cell_content_map
        if cell_content_map is None and cells_data:
            cell_content_map = BlockProcessor.build_cell_content_map(cells_data)

        # 获取表格矩阵
        table_matrix = BlockProcessor.table_to_matrix(block, cell_content_map)
        if not table_matrix:
            return ""

        # 生成Markdown表格
        markdown_lines = []
        for i, row in enumerate(table_matrix):
            # 转义管道符，空内容用空格代替
            escaped_row = [
                (cell.replace("|", "\\|") if cell else " ")
                for cell in row
            ]
            markdown_lines.append("| " + " | ".join(escaped_row) + " |")

            # 添加分隔行（第一行后）
            if i == 0:
                separator = "| " + " | ".join(["---"] * len(row)) + " |"
                markdown_lines.append(separator)

        return "\n".join(markdown_lines)

    @staticmethod
    def table_to_text(
        block: Dict[str, Any],
        cell_content_map: Optional[Dict[str, str]] = None,
        separator: str = " | ",
        include_structure: bool = True
    ) -> str:
        """
        将表格Block转换为纯文本格式

        职责：将表格数据格式化为易读的纯文本
        适用场景：文本搜索、简单展示、日志输出

        Args:
            block: 表格Block数据，应为表格类型（block_type=31）
            cell_content_map: 单元格ID到内容的映射字典（可选）
                             可通过 build_cell_content_map() 方法生成
            separator: 单元格之间的分隔符，默认为 " | "
            include_structure: 是否包含结构信息（行数×列数），默认True

        Returns:
            纯文本格式的表格内容
            如果表格数据无效则返回表格摘要

        Example:
            >>> table_block = {"block_type": 31, "table": {...}}
            >>> text = BlockProcessor.table_to_text(table_block, separator=", ")
            >>> print(text)
            [表格: 2行×3列]
            标题1, 标题2, 标题3
            数据1, 数据2, 数据3
        """
        table_info = BlockProcessor.extract_table_info(block)
        if not table_info:
            return "[表格]"

        # 获取表格矩阵
        table_matrix = BlockProcessor.table_to_matrix(block, cell_content_map)

        text_parts = []

        # 添加结构信息
        if include_structure:
            row_size = table_info["row_size"]
            column_size = table_info["column_size"]
            text_parts.append(f"[表格: {row_size}行×{column_size}列]")

        # 添加表格内容
        for row in table_matrix:
            # 过滤空内容
            row_text = separator.join([cell if cell else "" for cell in row])
            if row_text.strip():
                text_parts.append(row_text)

        return "\n".join(text_parts) if text_parts else "[表格]"

    @staticmethod
    def extract_text_from_block(block: Dict[str, Any]) -> str:
        """
        从Block中提取纯文本内容

        Args:
            block: Block数据字典

        Returns:
            提取的文本内容
        """
        block_type = block.get("block_type")
        text_parts = []

        # 处理文本类型的Block
        text_types = {
            1: "page",  # 页面
            2: "text",  # 文本
            3: "heading1",  # 一级标题
            4: "heading2",  # 二级标题
            5: "heading3",  # 三级标题
            6: "heading4",  # 四级标题
            7: "heading5",  # 五级标题
            8: "heading6",  # 六级标题
            9: "heading7",  # 七级标题
            10: "heading8",  # 八级标题
            11: "heading9",  # 九级标题
            12: "bullet",  # 无序列表
            13: "ordered",  # 有序列表
            14: "code",  # 代码块
            15: "quote",  # 引用
            17: "todo",  # 待办事项
        }

        if block_type in text_types:
            text_key = text_types[block_type]
            text_data = block.get(text_key, {})
            elements = text_data.get("elements", [])

            for element in elements:
                # 提取文本运行
                if "text_run" in element:
                    text_run = element["text_run"]
                    content = text_run.get("content", "")
                    if content:
                        url = text_run.get("text_element_style", {}).get("link", {}).get("url")
                        text_parts.append(f"[{content}]({url})" if url and block_type != 14 else content)

                # 提取@用户
                elif "mention_user" in element:
                    text_parts.append("[@用户]")

                # 提取@文档
                elif "mention_doc" in element:
                    mention_doc = element["mention_doc"]
                    title = mention_doc.get("title", "")
                    if title:
                        text_parts.append(f"[@文档: {title}]")
                    else:
                        text_parts.append("[@文档]")

                # 提取日期提醒
                elif "reminder" in element:
                    text_parts.append("[日期提醒]")

                # 提取公式
                elif "equation" in element:
                    equation = element["equation"]
                    content = equation.get("content", "")
                    if content:
                        text_parts.append(f"[公式: {content}]")

        # 处理图片Block
        elif block_type == BlockProcessor.BLOCK_TYPE_IMAGE:
            image_data = block.get("image", {})
            token = image_data.get("token", "")
            block_id_val = block.get("block_id", "")
            caption = image_data.get("caption", {}).get("content", "")
            if token and block_id_val:
                expected_path = f"feishu_images/{block_id_val[:20]}_{token[:20]}.png"
                label = f"图片: {expected_path}"
                if caption:
                    label += f" ({caption})"
                text_parts.append(f"[{label}]")
            elif caption:
                text_parts.append(f"[图片: {caption}]")
            else:
                text_parts.append("[图片]")

        # 处理流程图/UML
        elif block_type == BlockProcessor.BLOCK_TYPE_DIAGRAM:
            diagram_data = block.get("diagram", {})
            diagram_type = diagram_data.get("diagram_type", 0)
            diagram_name = {1: "流程图", 2: "UML图"}.get(diagram_type, "图表")
            text_parts.append(f"[{diagram_name}]")

        # 处理多维表格
        elif block_type == BlockProcessor.BLOCK_TYPE_BITABLE:
            text_parts.append("[多维表格]")

        # 处理电子表格
        elif block_type == BlockProcessor.BLOCK_TYPE_SHEET:
            text_parts.append("[电子表格]")

        # 处理思维笔记
        elif block_type == BlockProcessor.BLOCK_TYPE_MINDNOTE:
            text_parts.append("[思维笔记]")

        # 处理文件
        elif block_type == BlockProcessor.BLOCK_TYPE_FILE:
            file_data = block.get("file", {})
            file_name = file_data.get("name", "")
            if file_name:
                text_parts.append(f"[文件: {file_name}]")
            else:
                text_parts.append("[文件]")

        # 处理表格（类型31）
        # 注意：此方法只提取表格摘要，完整内容提取请使用 table_to_text() 或 table_to_markdown()
        elif block_type == BlockProcessor.BLOCK_TYPE_TABLE:
            text_parts.append(BlockProcessor.extract_table_summary(block))

        # 处理表格单元格
        elif block_type == BlockProcessor.BLOCK_TYPE_TABLE_CELL:
            # 表格单元格可能包含子块
            children = block.get("children", [])
            if children:
                # 递归提取子块文本
                for child_id in children:
                    # 注意：这里需要实际的子块数据，当前只能返回占位符
                    text_parts.append("[表格单元格]")

        # 处理高亮块
        elif block_type == BlockProcessor.BLOCK_TYPE_CALLOUT:
            callout_data = block.get("callout", {})
            # 高亮块可能有背景色和图标
            text_parts.append("[高亮块]")

        # 处理画板（类型43）
        elif block_type == BlockProcessor.BLOCK_TYPE_BOARD:
            text_parts.append(BlockProcessor.extract_board_summary(block))

        return "".join(text_parts)

    # ==================== 画板处理方法 ====================

    @staticmethod
    def extract_board_info(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从画板Block中提取画板元信息

        职责：提取画板的结构化信息，包括token等元数据

        Args:
            block: 画板Block的完整数据，必须包含 block_type=43

        Returns:
            画板元信息字典，包含：
            - block_id (str): Block的唯一标识
            - block_type (int): Block类型，固定为43
            - token (str): 画板的token，用于导出图片

            如果block不是画板类型，返回None

        Example:
            >>> block = {"block_id": "xxx", "block_type": 43, "board": {"token": "HCX..."}}
            >>> info = BlockProcessor.extract_board_info(block)
            >>> print(info)
            {'block_id': 'xxx', 'block_type': 43, 'token': 'HCX...'}
        """
        block_type = block.get("block_type")
        if block_type != BlockProcessor.BLOCK_TYPE_BOARD:
            return None

        block_id = block.get("block_id", "")
        board_data = block.get("board", {})

        return {
            "block_id": block_id,
            "block_type": block_type,
            "token": board_data.get("token", "")
        }

    @staticmethod
    def extract_board_summary(block: Dict[str, Any]) -> str:
        """
        从画板Block中提取简要文本描述

        职责：生成画板的可读文本摘要

        Args:
            block: 画板Block的完整数据

        Returns:
            画板的简要描述字符串，格式如：[画板: HCXEwkQO...]
            如果没有token则返回 [画板]

        Example:
            >>> block = {"block_type": 43, "board": {"token": "HCXEwkQOmh6CpEb"}}
            >>> summary = BlockProcessor.extract_board_summary(block)
            >>> print(summary)
            [画板: HCXEwkQOmh6CpEb]

        Note:
            - 若token超过20字符会截断显示
            - 用于文本提取场景，如extract_text_from_block
        """
        block_type = block.get("block_type")
        if block_type != BlockProcessor.BLOCK_TYPE_BOARD:
            return ""

        board_data = block.get("board", {})
        token = board_data.get("token", "")

        if token:
            if len(token) > 20:
                return f"[画板: {token[:20]}...]"
            return f"[画板: {token}]"
        return "[画板]"

    @staticmethod
    def get_board_download_token(block: Dict[str, Any]) -> Optional[str]:
        """
        从画板Block中获取可用于导出图片的token

        职责：提取画板token，供download_board_as_image工具使用

        Args:
            block: 画板Block的完整数据

        Returns:
            画板的token字符串，可直接用于API调用
            如果block不是画板类型或没有token，返回None

        Example:
            >>> block = {"block_type": 43, "board": {"token": "HCXEwkQOmh6CpEb"}}
            >>> token = BlockProcessor.get_board_download_token(block)
            >>> # 使用token下载画板图片
            >>> download_board_as_image(board_tokens=[token])

        Note:
            此方法专门为download_board_as_image工具设计
            返回的token可直接作为board_tokens参数使用
        """
        block_type = block.get("block_type")
        if block_type != BlockProcessor.BLOCK_TYPE_BOARD:
            return None

        board_data = block.get("board", {})
        token = board_data.get("token")

        return token if token else None

    @staticmethod
    def extract_text_from_blocks(blocks: List[Dict[str, Any]], include_structure: bool = True) -> str:
        """
        从多个Block中提取所有文本内容

        Args:
            blocks: Block列表
            include_structure: 是否包含结构信息（如标题层级）

        Returns:
            提取的文本内容
        """
        text_parts = []

        for block in blocks:
            block_type = block.get("block_type")
            text = BlockProcessor.extract_text_from_block(block)

            if include_structure:
                # 添加结构信息
                if block_type == 3:  # heading1
                    text_parts.append(f"# {text}\n")
                elif block_type == 4:  # heading2
                    text_parts.append(f"## {text}\n")
                elif block_type == 5:  # heading3
                    text_parts.append(f"### {text}\n")
                elif block_type == 6:  # heading4
                    text_parts.append(f"#### {text}\n")
                elif block_type == 7:  # heading5
                    text_parts.append(f"##### {text}\n")
                elif block_type == 8:  # heading6
                    text_parts.append(f"###### {text}\n")
                elif block_type == 12:  # bullet
                    text_parts.append(f"- {text}\n")
                elif block_type == 13:  # ordered
                    text_parts.append(f"1. {text}\n")
                elif block_type == 14:  # code
                    text_parts.append(f"```\n{text}\n```\n")
                elif block_type == 15:  # quote
                    text_parts.append(f"> {text}\n")
                elif block_type == 17:  # todo
                    text_parts.append(f"- [ ] {text}\n")
                else:
                    if text:
                        text_parts.append(f"{text}\n")
            else:
                if text:
                    text_parts.append(text)

        return "\n".join(text_parts) if include_structure else " ".join(text_parts)

    @staticmethod
    def extract_text_with_media_markers(
        blocks: List[Dict[str, Any]],
        include_structure: bool = True,
        include_position: bool = True
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        从多个Block中提取文本内容，并在媒体位置插入带有文件路径的标记

        这个方法是 extract_text_from_blocks 的增强版，专门用于需要关联图片/画板位置的场景。
        返回的文本中会包含形如 `[📷 图片: feishu_images/xxx.png - 所属章节]` 的标记，
        使 cursor 能够通过文件路径精确找到对应的图片。

        **核心设计**（v2.1 改进）：
        - 使用**文件路径**作为唯一标识（而非序号）
        - 文件路径在下载前就能确定（基于 block_id + token）
        - 即使某张图片下载失败，也不会影响其他图片的对应关系
        - cursor 可以通过文件路径直接读取图片文件

        Args:
            blocks: Block列表
            include_structure: 是否包含结构信息（如标题层级）
            include_position: 是否在标记中包含位置索引

        Returns:
            Tuple[str, List[Dict]]:
                - str: 提取的文本内容（含媒体位置标记）
                - List[Dict]: 媒体元数据列表，每个元素包含：
                    - index: 媒体序号（从1开始，仅供参考）
                    - media_type: "image" | "board" | "diagram" 等
                    - block_id: block的唯一标识
                    - token: 媒体的token（用于下载）
                    - expected_filename: 预期的文件名（唯一标识）
                    - section_path: 所属章节路径
                    - context_before: 前一个block的文本摘要
                    - context_after: 后一个block的文本摘要

        Example:
            >>> blocks = [...]
            >>> text, media_list = BlockProcessor.extract_text_with_media_markers(blocks)
            >>> print(text)
            ## 需求背景
            这是一段描述文字...

            [📷 图片: feishu_images/doxcn123_abc456.png - 需求背景]

            继续后面的文字...
        """
        text_parts = []
        media_list = []
        media_index = 0  # 媒体序号计数器

        # 第一遍：收集所有标题，用于确定每个媒体所属的章节
        heading_stack = []  # [(level, text, position), ...]
        heading_types = {3, 4, 5, 6, 7, 8, 9, 10, 11}  # heading1-9

        for idx, block in enumerate(blocks):
            block_type = block.get("block_type")
            block_id = block.get("block_id", "")

            # 更新标题栈
            if block_type in heading_types:
                level = block_type - 2  # heading1=3, 所以level=1
                heading_text = BlockProcessor.extract_text_from_block(block)
                if heading_text:
                    # 移除同级或更低级的标题
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, heading_text, idx))

            # 检查是否是媒体类型
            media_info = BlockProcessor._extract_media_info(block, idx)

            if media_info:
                media_index += 1
                media_info["index"] = media_index

                # 🆕 预计算文件名（关键改进：文件名在下载前就能确定）
                token = media_info.get("token", "")
                media_type = media_info.get("media_type", "unknown")

                # 文件名格式与下载时保持一致
                if media_type == "board":
                    expected_filename = f"board_{block_id[:20]}_{token[:20]}.png"
                else:
                    expected_filename = f"{block_id[:20]}_{token[:20]}.png"

                media_info["expected_filename"] = expected_filename
                media_info["expected_path"] = f"feishu_images/{expected_filename}"

                # 获取上下文
                context_before = ""
                context_after = ""

                if idx > 0:
                    prev_text = BlockProcessor.extract_text_from_block(blocks[idx - 1])
                    context_before = prev_text[:100] if prev_text else ""

                if idx < len(blocks) - 1:
                    next_text = BlockProcessor.extract_text_from_block(blocks[idx + 1])
                    context_after = next_text[:100] if next_text else ""

                media_info["context_before"] = context_before
                media_info["context_after"] = context_after

                # 获取所属章节
                section_path = " > ".join([h[1] for h in heading_stack]) if heading_stack else ""
                media_info["section_path"] = section_path

                media_list.append(media_info)

                # 🆕 生成基于文件路径的媒体标记（关键改进！）
                type_emoji = {"image": "📷", "board": "🎨", "diagram": "📊", "mindnote": "🧠"}.get(media_type, "📎")
                type_name = {"image": "图片", "board": "画板", "diagram": "流程图", "mindnote": "思维导图"}.get(media_type, "媒体")

                # 简短的章节提示
                section_hint = f" - {heading_stack[-1][1][:15]}" if heading_stack else ""

                # 🆕 使用文件路径作为标识（而非序号）
                # 格式：[📷 图片: feishu_images/xxx.png - 需求背景]
                readable_marker = f"[{type_emoji} {type_name}: {media_info['expected_path']}{section_hint}]"

                # 技术标记也包含文件路径
                tech_marker = f"<!--MEDIA:{media_type}:file={media_info['expected_path']}:block_id={block_id}-->"

                text_parts.append(f"\n{tech_marker}\n{readable_marker}\n")
                continue

            # 非媒体类型，正常处理
            text = BlockProcessor.extract_text_from_block(block)

            if include_structure:
                if block_type == 3:  # heading1
                    text_parts.append(f"# {text}\n")
                elif block_type == 4:  # heading2
                    text_parts.append(f"## {text}\n")
                elif block_type == 5:  # heading3
                    text_parts.append(f"### {text}\n")
                elif block_type == 6:  # heading4
                    text_parts.append(f"#### {text}\n")
                elif block_type == 7:  # heading5
                    text_parts.append(f"##### {text}\n")
                elif block_type == 8:  # heading6
                    text_parts.append(f"###### {text}\n")
                elif block_type == 12:  # bullet
                    text_parts.append(f"- {text}\n")
                elif block_type == 13:  # ordered
                    text_parts.append(f"1. {text}\n")
                elif block_type == 14:  # code
                    text_parts.append(f"```\n{text}\n```\n")
                elif block_type == 15:  # quote
                    text_parts.append(f"> {text}\n")
                elif block_type == 17:  # todo
                    text_parts.append(f"- [ ] {text}\n")
                else:
                    if text:
                        text_parts.append(f"{text}\n")
            else:
                if text:
                    text_parts.append(text)

        result_text = "\n".join(text_parts) if include_structure else " ".join(text_parts)
        return result_text, media_list

    @staticmethod
    def _build_media_marker(media_info: Dict[str, Any], heading_stack: List[Tuple[int, str, int]]) -> Tuple[str, str]:
        """基于媒体信息构建可读标记和技术标记。"""
        media_type = media_info.get("media_type", "unknown")
        block_id = media_info.get("block_id", "")
        expected_path = media_info.get("expected_path", "")
        type_emoji = {"image": "📷", "board": "🎨", "diagram": "📊", "mindnote": "🧠"}.get(media_type, "📎")
        type_name = {"image": "图片", "board": "画板", "diagram": "流程图", "mindnote": "思维导图"}.get(media_type, "媒体")
        section_hint = f" - {heading_stack[-1][1][:15]}" if heading_stack else ""
        readable_marker = f"[{type_emoji} {type_name}: {expected_path}{section_hint}]"
        tech_marker = f"<!--MEDIA:{media_type}:file={expected_path}:block_id={block_id}-->"
        return readable_marker, tech_marker

    @staticmethod
    def _extract_table_cell_text_with_media(
        cell_block: Dict[str, Any],
        block_map: Dict[str, Dict[str, Any]],
        heading_stack: List[Tuple[int, str, int]],
        media_list: List[Dict[str, Any]],
        media_seen: Set[str],
    ) -> str:
        """递归提取单元格文本，并将单元格内媒体转换为锚点。"""
        queue: List[str] = list(reversed(cell_block.get("children", []) or []))
        visited: Set[str] = set()
        fragments: List[str] = []
        while queue:
            current_id = queue.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            item = block_map.get(current_id)
            if not item:
                continue

            media_info = BlockProcessor._extract_media_info(item, 0)
            if media_info:
                token = media_info.get("token", "")
                media_type = media_info.get("media_type", "unknown")
                if media_type == "board":
                    expected_filename = f"board_{current_id[:20]}_{token[:20]}.png"
                else:
                    expected_filename = f"{current_id[:20]}_{token[:20]}.png"
                media_info["expected_filename"] = expected_filename
                media_info["expected_path"] = f"feishu_images/{expected_filename}"
                media_info["section_path"] = " > ".join([h[1] for h in heading_stack]) if heading_stack else ""

                if current_id not in media_seen:
                    media_seen.add(current_id)
                    media_info["index"] = len(media_list) + 1
                    media_list.append(media_info)

                readable_marker, _ = BlockProcessor._build_media_marker(media_info, heading_stack)
                fragments.append(readable_marker)
            else:
                text = BlockProcessor.extract_text_from_block(item).strip()
                if text and text not in ("[表格单元格]",):
                    fragments.append(text)

            for child_id in reversed(item.get("children", []) or []):
                if child_id not in visited:
                    queue.append(child_id)

        if not fragments:
            return ""

        return "<br>".join(fragments)

    @staticmethod
    def extract_text_with_media_markers_and_tables(
        blocks: List[Dict[str, Any]],
        include_structure: bool = True
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        提取文本并插入媒体锚点，同时对表格做递归展开（含单元格内媒体）。
        """
        text_parts: List[str] = []
        media_list: List[Dict[str, Any]] = []
        media_seen: Set[str] = set()
        heading_stack: List[Tuple[int, str, int]] = []
        heading_types = {3, 4, 5, 6, 7, 8, 9, 10, 11}
        block_map = {b.get("block_id"): b for b in blocks if b.get("block_id")}

        table_descendants: Set[str] = set()
        for block in blocks:
            if block.get("block_type") != BlockProcessor.BLOCK_TYPE_TABLE:
                continue
            queue = list(block.get("table", {}).get("cells", []) or [])
            local_visited: Set[str] = set()
            while queue:
                bid = queue.pop()
                if not bid or bid in local_visited:
                    continue
                local_visited.add(bid)
                table_descendants.add(bid)
                child_block = block_map.get(bid)
                if child_block:
                    queue.extend(child_block.get("children", []) or [])

        for idx, block in enumerate(blocks):
            block_id = block.get("block_id", "")
            block_type = block.get("block_type")

            if block_type in heading_types:
                level = block_type - 2
                heading_text = BlockProcessor.extract_text_from_block(block)
                if heading_text:
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, heading_text, idx))

            # 表格内部节点由表格统一渲染，避免占位符和重复输出
            if block_id in table_descendants and block_type != BlockProcessor.BLOCK_TYPE_TABLE:
                continue

            if block_type == BlockProcessor.BLOCK_TYPE_TABLE:
                cell_ids = block.get("table", {}).get("cells", []) or []
                cell_content_map: Dict[str, str] = {}
                for cid in cell_ids:
                    cell_block = block_map.get(cid)
                    if not cell_block:
                        continue
                    cell_content_map[cid] = BlockProcessor._extract_table_cell_text_with_media(
                        cell_block=cell_block,
                        block_map=block_map,
                        heading_stack=heading_stack,
                        media_list=media_list,
                        media_seen=media_seen,
                    )

                table_md = BlockProcessor.table_to_markdown(block, cell_content_map=cell_content_map)
                if table_md:
                    text_parts.append(f"\n{table_md}\n")
                else:
                    text_parts.append(f"{BlockProcessor.extract_table_summary(block)}\n")
                continue

            media_info = BlockProcessor._extract_media_info(block, idx)
            if media_info:
                token = media_info.get("token", "")
                media_type = media_info.get("media_type", "unknown")
                if media_type == "board":
                    expected_filename = f"board_{block_id[:20]}_{token[:20]}.png"
                else:
                    expected_filename = f"{block_id[:20]}_{token[:20]}.png"
                media_info["expected_filename"] = expected_filename
                media_info["expected_path"] = f"feishu_images/{expected_filename}"
                media_info["section_path"] = " > ".join([h[1] for h in heading_stack]) if heading_stack else ""
                media_info["context_before"] = ""
                media_info["context_after"] = ""

                if block_id not in media_seen:
                    media_seen.add(block_id)
                    media_info["index"] = len(media_list) + 1
                    media_list.append(media_info)

                readable_marker, tech_marker = BlockProcessor._build_media_marker(media_info, heading_stack)
                text_parts.append(f"\n{tech_marker}\n{readable_marker}\n")
                continue

            text = BlockProcessor.extract_text_from_block(block)
            if include_structure:
                if block_type == 3:
                    text_parts.append(f"# {text}\n")
                elif block_type == 4:
                    text_parts.append(f"## {text}\n")
                elif block_type == 5:
                    text_parts.append(f"### {text}\n")
                elif block_type == 6:
                    text_parts.append(f"#### {text}\n")
                elif block_type == 7:
                    text_parts.append(f"##### {text}\n")
                elif block_type == 8:
                    text_parts.append(f"###### {text}\n")
                elif block_type == 12:
                    text_parts.append(f"- {text}\n")
                elif block_type == 13:
                    text_parts.append(f"1. {text}\n")
                elif block_type == 14:
                    text_parts.append(f"```\n{text}\n```\n")
                elif block_type == 15:
                    text_parts.append(f"> {text}\n")
                elif block_type == 17:
                    text_parts.append(f"- [ ] {text}\n")
                else:
                    if text:
                        text_parts.append(f"{text}\n")
            else:
                if text:
                    text_parts.append(text)

        return "\n".join(text_parts), media_list

    @staticmethod
    def _extract_media_info(block: Dict[str, Any], position: int) -> Optional[Dict[str, Any]]:
        """
        从Block中提取媒体信息（内部方法）

        Args:
            block: Block数据
            position: 在blocks列表中的位置索引

        Returns:
            媒体信息字典，如果不是媒体类型则返回None
        """
        block_type = block.get("block_type")
        block_id = block.get("block_id", "")

        # 图片
        if block_type == BlockProcessor.BLOCK_TYPE_IMAGE:
            image_data = block.get("image", {})
            return {
                "media_type": "image",
                "block_id": block_id,
                "position": position,
                "token": image_data.get("token", ""),
                "width": image_data.get("width"),
                "height": image_data.get("height"),
                "caption": image_data.get("caption", {}).get("content", "")
            }

        # 画板
        elif block_type == BlockProcessor.BLOCK_TYPE_BOARD:
            board_data = block.get("board", {})
            return {
                "media_type": "board",
                "block_id": block_id,
                "position": position,
                "token": board_data.get("token", "")
            }

        # 流程图/UML
        elif block_type == BlockProcessor.BLOCK_TYPE_DIAGRAM:
            diagram_data = block.get("diagram", {})
            return {
                "media_type": "diagram",
                "block_id": block_id,
                "position": position,
                "diagram_type": diagram_data.get("diagram_type", 0)
            }

        # 思维笔记
        elif block_type == BlockProcessor.BLOCK_TYPE_MINDNOTE:
            mindnote_data = block.get("mindnote", {})
            return {
                "media_type": "mindnote",
                "block_id": block_id,
                "position": position,
                "token": mindnote_data.get("token", "")
            }

        return None

    @staticmethod
    def get_media_context(
        blocks: List[Dict[str, Any]],
        block_id: str,
        context_blocks: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定媒体block的上下文信息

        Args:
            blocks: 完整的Block列表
            block_id: 要查找的媒体block_id
            context_blocks: 上下文block数量（前后各取几个）

        Returns:
            上下文信息字典，包含：
            - found: 是否找到
            - position: 位置索引
            - media_info: 媒体信息
            - context_before: 前面的文本内容
            - context_after: 后面的文本内容
            - parent_heading: 所属的最近标题
            - section_path: 章节路径（如 "需求背景 > 功能描述"）
        """
        # 查找目标block的位置
        target_idx = None
        for idx, block in enumerate(blocks):
            if block.get("block_id") == block_id:
                target_idx = idx
                break

        if target_idx is None:
            return {"found": False, "error": f"未找到block_id: {block_id}"}

        target_block = blocks[target_idx]
        media_info = BlockProcessor._extract_media_info(target_block, target_idx)

        if not media_info:
            return {"found": False, "error": f"block_id {block_id} 不是媒体类型"}

        # 构建表格后代集合，排除表格单元格内的标题块影响 section_path
        block_map = {b.get("block_id"): b for b in blocks if b.get("block_id")}
        table_descendants: set = set()
        for blk in blocks:
            if blk.get("block_type") != BlockProcessor.BLOCK_TYPE_TABLE:
                continue
            queue = list(blk.get("table", {}).get("cells", []) or [])
            visited_local: set = set()
            while queue and len(visited_local) < 2000:
                bid = queue.pop(0)
                if not bid or bid in visited_local:
                    continue
                visited_local.add(bid)
                table_descendants.add(bid)
                child_blk = block_map.get(bid)
                if child_blk:
                    queue.extend(child_blk.get("children", []) or [])

        # 提取前面的上下文
        context_before_parts = []
        start_idx = max(0, target_idx - context_blocks)
        for i in range(start_idx, target_idx):
            text = BlockProcessor.extract_text_from_block(blocks[i])
            if text:
                context_before_parts.append(text)

        # 提取后面的上下文
        context_after_parts = []
        end_idx = min(len(blocks), target_idx + context_blocks + 1)
        for i in range(target_idx + 1, end_idx):
            text = BlockProcessor.extract_text_from_block(blocks[i])
            if text:
                context_after_parts.append(text)

        # 查找所属标题（向前遍历找最近的标题，跳过表格内标题）
        parent_heading = None
        section_path_parts = []
        heading_types = {3, 4, 5, 6, 7, 8, 9, 10, 11}  # heading1-9
        # 只接受比当前最高级别更高的标题（block_type 值更小 = 层级更高）
        # 避免同级/子级的兄弟标题被累积进 section_path
        min_level = float('inf')  # 已收集标题中 block_type 的最小值

        for i in range(target_idx - 1, -1, -1):
            block = blocks[i]
            block_type = block.get("block_type")
            bid = block.get("block_id", "")
            # 跳过处于表格单元格内的标题，避免污染 section_path
            if bid in table_descendants:
                continue
            if block_type in heading_types:
                # 只收录比当前路径最高层级更高的标题（即真正的父级）
                if block_type >= min_level:
                    continue
                heading_text = BlockProcessor.extract_text_from_block(block)
                if heading_text:
                    if parent_heading is None:
                        parent_heading = {
                            "level": block_type - 2,  # heading1=3, 所以level=1
                            "text": heading_text,
                            "block_id": bid
                        }
                    section_path_parts.insert(0, heading_text)
                    min_level = block_type
                    # 找到一级标题就停止
                    if block_type == 3:
                        break

        return {
            "found": True,
            "position": target_idx,
            "media_info": media_info,
            "context_before": "\n".join(context_before_parts),
            "context_after": "\n".join(context_after_parts),
            "parent_heading": parent_heading,
            "section_path": " > ".join(section_path_parts) if section_path_parts else None
        }
