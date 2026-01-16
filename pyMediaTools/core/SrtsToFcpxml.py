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
    
def SrtsToFcpxml(source_srt, trans_srts, save_path, seamless_fcpxml):
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
    
    # 创建 FCPXML 的根元素
    fcpxml = ET.Element('fcpxml', version="1.9")
    resources = ET.SubElement(fcpxml, 'resources')
    format_attrs = {
                "name": "FFVideoFormat1080p30",
                "frameDuration": "1/30s",
                "width": "1920",
                "height": "1080",
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
    
    duration = get_Fraction_time(source_subs[-1].end.ordinal)
    sequence = ET.SubElement(project, 'sequence', tcFormat="NDF", tcStart="0/1s", duration=duration, format="r0")
    
    spine = ET.SubElement(sequence, 'spine')

    title_list = []
    total_index = 0
    pre_sub_end = 0
    for i in range(count):
        source_sub = source_subs[i]
        if not seamless_fcpxml:
            if pre_sub_end < source_sub.start.ordinal:
                offset = get_Fraction_time(pre_sub_end)
                duration = source_sub.start.ordinal - pre_sub_end
                duration = get_Fraction_time(duration)
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
        
        startStr = get_Fraction_time(start)
        duration = source_sub.duration.ordinal
        if seamless_fcpxml and i < count - 1:
            next_sub = source_subs[i + 1]
            duration = next_sub.start.ordinal - start
        
        durationStr = get_Fraction_time(duration)
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
        text_style_attrs = {
            "alignment": subtitle_setting.get("source_alignment", "center"),
            "fontColor": subtitle_setting.get("source_fontColor", "1 1 1 1"),
            "bold": subtitle_setting.get("source_bold", "0"),
            "strokeColor": subtitle_setting.get("source_strokeColor", "1 1 1 1"),
            "font": subtitle_setting.get("source_font", "Arial"),
            "fontSize": subtitle_setting.get("source_fontSize", "50"),
            "italic": subtitle_setting.get("source_italic", "0"),
            "strokeWidth": subtitle_setting.get("source_strokeWidth", "0"),
            "lineSpacing": subtitle_setting.get("source_lineSpacing", "0")
        }
        text_style2 = ET.SubElement(text_style_def, 'text-style', attrib=text_style_attrs)
        
        adjust_conform = ET.SubElement(title, 'adjust-conform', type="fit")
        posY = subtitle_setting.get("source_pos", "-45")
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
            startStr = get_Fraction_time(start)
            duration = trans_sub.duration.ordinal
            if seamless_fcpxml and i < count - 1:
                next_sub = trans_subs[i + 1]
                duration = next_sub.start.ordinal - start
            durationStr = get_Fraction_time(duration)
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
            text_style_attrs = {
                "alignment": subtitle_setting.get("trans_alignment", "center"),
                "fontColor": subtitle_setting.get("trans_fontColor", "1 1 1 1"),
                "bold": subtitle_setting.get("trans_bold", "0"),
                "strokeColor": subtitle_setting.get("trans_strokeColor", "1 1 1 1"),
                "font": subtitle_setting.get("trans_font", "Arial"),
                "fontSize": subtitle_setting.get("trans_fontSize", "50"),
                "italic": subtitle_setting.get("trans_italic", "0"),
                "strokeWidth": subtitle_setting.get("trans_strokeWidth", "0"),
                "lineSpacing": subtitle_setting.get("trans_lineSpacing", "0")
            }
            text_style2 = ET.SubElement(text_style_def, 'text-style', attrib=text_style_attrs)
            
            adjust_conform = ET.SubElement(child_title, 'adjust-conform', type="fit")
            posY = subtitle_setting.get("trans_pos", "-38")
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