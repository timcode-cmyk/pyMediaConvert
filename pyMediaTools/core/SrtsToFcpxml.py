import os
import json
import math

import xml.etree.ElementTree as ET
from fractions import Fraction

import pysrt

subtitle_setting = {}

def indent(elem, level=0):
    """对 XML 元素进行缩进格式化"""
    i = "\n" + "\t" * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
            
def get_project_name(path):
    file_name = os.path.basename(path)
    file_name = file_name[3:-7]
    return file_name
    
def get_Fraction_time(time, fps=30):
    """ 把srt时间(ms),根据帧率转换为分数形式的秒字符串 """
    frame = math.floor(time / (1000 / fps));
    frac = Fraction(frame * 100, fps * 100)
    ret = f"{frac.numerator}/{frac.denominator}s"
    
    return ret

def format_color(color):
    if isinstance(color, (list, tuple)):
        return f"{color[0]} {color[1]} {color[2]} {color[3]}"
    return str(color)

def get_style_attributes(style_dict, prefix, subtitle_setting):
    def g(key, default):
        # 优先从传入的 style_dict 获取，否则从 subtitle_setting (JSON配置) 获取，最后使用默认值
        val = style_dict.get(key)
        if val is not None:
            return val
        return subtitle_setting.get(f"{prefix}_{key}", default)

    # 颜色处理
    font_color = format_color(g("fontColor", "1 1 1 1"))
    stroke_color = format_color(g("strokeColor", "1 1 1 1"))
    shadow_color = format_color(g("shadowColor", "0 0 0 0.5"))
    bg_color = format_color(g("backgroundColor", "0 0 0 0"))
    
    # 布尔值处理
    bold = "1" if g("bold", False) else "0"
    italic = "1" if g("italic", False) else "0"
    
    # 数值处理
    font_size = str(g("fontSize", "50"))
    line_spacing = str(g("lineSpacing", "0"))
    stroke_width = float(g("strokeWidth", "0"))
    
    # 阴影偏移处理: (x, y) -> "距离 角度"
    shadow_offset_raw = g("shadowOffset", (2, 2))
    if isinstance(shadow_offset_raw, (list, tuple)):
        x, y = shadow_offset_raw
    else:
        try:
            parts = str(shadow_offset_raw).split()
            x, y = float(parts[0]), float(parts[1])
        except:
            x, y = 2, 2
    
    dist = math.sqrt(x*x + y*y)
    # atan2 返回弧度，转换为角度。FCP中0度向右，顺时针增加。
    angle = math.degrees(math.atan2(y, x))
    if angle < 0: angle += 360
    shadow_offset_str = f"{dist:.1f} {angle:.1f}"

    # 自动开关逻辑
    if "useStroke" in style_dict:
        use_stroke = "1" if style_dict["useStroke"] else "0"
    else:
        use_stroke = "1" if stroke_width > 0 else "0"
    
    # 检查阴影透明度
    if "useShadow" in style_dict:
        use_shadow = "1" if style_dict["useShadow"] else "0"
    else:
        try: s_a = float(shadow_color.split()[3])
        except: s_a = 0
        use_shadow = "1" if s_a > 0 else "0"
    
    # 检查背景透明度
    if "useBackground" in style_dict:
        use_background = "1" if style_dict["useBackground"] else "0"
    else:
        try: b_a = float(bg_color.split()[3])
        except: b_a = 0
        use_background = "1" if b_a > 0 else "0"

    return {
        "alignment": str(g("alignment", "center")),
        "fontColor": font_color,
        "bold": bold,
        "italic": italic,
        "font": str(g("font", "Arial")),
        "fontSize": font_size,
        "lineSpacing": line_spacing,
        
        "strokeColor": stroke_color,
        "strokeWidth": str(stroke_width),
        "useStroke": use_stroke,
        
        "shadowColor": shadow_color,
        "shadowOffset": shadow_offset_str,
        "useDropShadow": use_shadow,
        
        "backgroundColor": bg_color,
        "useBackground": use_background,
    }
    
def SrtsToFcpxml(source_srt, trans_srts, save_path, seamless_fcpxml, xml_style_settings=None, video_settings=None):
    """ 把多个srt文件转换到一个fcpxml文件中 """
    
    # source_subs = pysrt.open(source_srt)
    source_subs = pysrt.from_string(source_srt)
    count = len(source_subs)
    if count == 0:
        print("Srt 字幕长度为0")
        return
    
    global subtitle_setting
    if os.path.exists("subtitle_pref.json"):
        with open("subtitle_pref.json", "r") as f:
            subtitle_setting = json.load(f)
    
    fps = video_settings.get('fps', 30) if video_settings else 30
    width = video_settings.get('width', 1920) if video_settings else 1920
    height = video_settings.get('height', 1080) if video_settings else 1080

    # 创建 FCPXML 的根元素
    fcpxml = ET.Element('fcpxml', version="1.9")
    resources = ET.SubElement(fcpxml, 'resources')
    frame_duration = Fraction(1, fps)
    format_attrs = {
                "name": f"FFVideoFormat{height}p{fps}",
                "frameDuration": f"{frame_duration.numerator}/{frame_duration.denominator}s",
                "width": str(width),
                "height": str(height),
                "id": "r0"
            }
    resources_format = ET.SubElement(resources, 'format', attrib=format_attrs)
    effect_attrs = {
                "name": "Basic Title",
                "uid": ".../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti",
                "id": "r1"
            }
    resources_effect = ET.SubElement(resources, 'effect', attrib=effect_attrs)
    
    
    project_name = get_project_name(save_path)
    library = ET.SubElement(fcpxml, 'library')
    event = ET.SubElement(library, 'event', name=f"{project_name}")
    project = ET.SubElement(event, 'project', name=f"{project_name}")
    
    duration = get_Fraction_time(source_subs[-1].end.ordinal, fps)
    sequence = ET.SubElement(project, 'sequence', tcFormat="NDF", tcStart="0/1s", duration=duration, format="r0")
    
    spine = ET.SubElement(sequence, 'spine')

    title_list = []
    total_index = 0
    pre_sub_end = 0
    for i in range(count):
        source_sub = source_subs[i]
        if not seamless_fcpxml:
            if pre_sub_end < source_sub.start.ordinal:
                offset = get_Fraction_time(pre_sub_end, fps)
                duration = source_sub.start.ordinal - pre_sub_end
                duration = get_Fraction_time(duration, fps)
                gap_attrs = {
                    "name": "Gap",
                    "start": "3600/1s",
                    "offset": offset,
                    "duration": duration
                }
                gap = ET.SubElement(spine, 'gap', attrib=gap_attrs)
                
        
        start = source_sub.start.ordinal
        if seamless_fcpxml and source_sub.start.ordinal > 34:
            start = source_sub.start.ordinal - 34
        
        startStr = get_Fraction_time(start, fps)
        duration = source_sub.duration.ordinal
        if seamless_fcpxml and i < count - 1:
            next_sub = source_subs[i + 1]
            duration = next_sub.start.ordinal - start
        
        durationStr = get_Fraction_time(duration, fps)
        title_attrs = {
            "name": "Subtitle",
            "ref": "r1",
            "enabled": "1",
            "start": startStr,
            "offset": startStr,
            "duration": durationStr
        }
        
        title = ET.SubElement(spine, 'title', attrib=title_attrs)
        
        text = ET.SubElement(title, 'text', attrib={"roll-up-height":"0"})
        text_style = ET.SubElement(text, 'text-style', ref=f"ts{total_index}")
        text_style.text = source_sub.text.strip().replace("@", "\n")
        
        text_style_def = ET.SubElement(title, 'text-style-def', id=f"ts{total_index}")
        
        # 获取样式配置 (优先使用传入的 xml_style_settings)
        src_style = xml_style_settings.get('source', {}) if xml_style_settings else {}
        
        text_style_attrs = get_style_attributes(src_style, "source", subtitle_setting)
        text_style2 = ET.SubElement(text_style_def, 'text-style', attrib=text_style_attrs)
        
        adjust_conform = ET.SubElement(title, 'adjust-conform', type="fit")
        posY = str(src_style.get("pos", subtitle_setting.get("source_pos", "-45")))
        adjust_transform = ET.SubElement(title, 'adjust-transform', scale="1 1", position=f"0 {posY}", anchor="0 0")
        
        total_index += 1
        pre_sub_end = source_sub.end.ordinal
        title_list.append(title)
        
    lane = 1
    for trans_srt in trans_srts:
        # trans_subs = pysrt.open(trans_srt)
        trans_subs = pysrt.from_string(trans_srt)
        for i in range(count):
            if i >= len(trans_subs):
                break
                
            trans_sub = trans_subs[i]
            title = title_list[i]
            
            start = trans_sub.start.ordinal
            if seamless_fcpxml and trans_sub.start.ordinal > 34:
                start = trans_sub.start.ordinal - 34
            startStr = get_Fraction_time(start, fps)
            duration = trans_sub.duration.ordinal
            if seamless_fcpxml and i < count - 1:
                next_sub = trans_subs[i + 1]
                duration = next_sub.start.ordinal - start
            durationStr = get_Fraction_time(duration, fps)
            title_attrs = {
                "name": "Subtitle",
                "lane": str(lane),
                "ref": "r1",
                "enabled": "1",
                "start": startStr,
                "offset": startStr,
                "duration": durationStr
            }
            
            child_title = ET.SubElement(title, 'title', attrib=title_attrs)
            
            text = ET.SubElement(child_title, 'text', attrib={"roll-up-height":"0"})
            text_style = ET.SubElement(text, 'text-style', ref=f"ts{total_index}")
            text_style.text = trans_sub.text.strip().replace("@", "\n")
            
            text_style_def = ET.SubElement(child_title, 'text-style-def', id=f"ts{total_index}")
            
            trans_style = xml_style_settings.get('translate', {}) if xml_style_settings else {}
            
            text_style_attrs = get_style_attributes(trans_style, "trans", subtitle_setting)
            text_style2 = ET.SubElement(text_style_def, 'text-style', attrib=text_style_attrs)
            
            adjust_conform = ET.SubElement(child_title, 'adjust-conform', type="fit")
            posY = str(trans_style.get("pos", subtitle_setting.get("trans_pos", "-38")))
            adjust_transform = ET.SubElement(child_title, 'adjust-transform', scale="1 1", position=f"0 {posY}", anchor="0 0")
            
            total_index += 1
            
        lane += 1
        
    
    # 缩进格式化
    indent(fcpxml)
    # 转换为字符串并写入文件
    tree = ET.ElementTree(fcpxml)
    tree.write(save_path, encoding='utf-8', xml_declaration=True)
    
    
if __name__ == '__main__':
    srt_path = r"C:\Users\Admin\Desktop\testSrt\source.srt"
    translate_path = r"C:\Users\Admin\Desktop\testSrt\translate.srt"
    translate2_path = r"C:\Users\Admin\Desktop\testSrt\translate2.srt"
    fcpxml_path = r"C:\Users\Admin\Desktop\test_output.fcpxml"
    

    # 解析 SRT 并生成 FCPXML
    SrtsToFcpxml(srt_path, [translate_path, translate2_path], fcpxml_path)

    print(f"FCPXML 文件已生成：{fcpxml_path}")