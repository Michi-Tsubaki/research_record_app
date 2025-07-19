#!./venv/bin/python3

import os
from flask import Flask, render_template, request, redirect, url_for, send_file
import json
import os
import hashlib
import shutil
import uuid
from datetime import datetime
import textwrap
import matplotlib.pyplot as plt
from PIL import Image
import matplotlib.font_manager as fm
import tempfile
import base64
import webbrowser
import time
import threading

class ResearchDiaryCore:
    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.images_dir = os.path.join(self.script_dir, "images")
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)

        self.data_file = os.path.join(self.script_dir, "research_data.json")
        self.draft_file = os.path.join(self.script_dir, "research_drafts.json")
        self.html_file = os.path.join(self.script_dir, "research_data.html")

        self.entries = []
        self.drafts = []

        self.setup_fonts()
        self.load_data()

    def setup_fonts(self):
        """日本語フォントの設定 (matplotlib用)"""
        try:
            font_paths = [
                "C:/Windows/Fonts/msgothic.ttc", "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc", "/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/Arial Unicode MS.ttf",
                "/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
                "/usr/share/fonts/truetype/vlgothic/VL-PGothic-Regular.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ]

            self.font_path = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    self.font_path = font_path
                    break

            if self.font_path:
                font_prop = fm.FontProperties(fname=self.font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                fm.fontManager.addfont(self.font_path) # Ensure font is added
            else:
                available_fonts = [f.name for f in fm.fontManager.ttflist]
                japanese_fonts = [
                    'Noto Sans CJK JP', 'Noto Sans JP', 'Takao PGothic',
                    'VL PGothic', 'IPAexGothic', 'IPAGothic', 'Hiragino Sans GB',
                    'Meiryo', 'MS Gothic', 'Yu Gothic'
                ]
                for font in japanese_fonts:
                    if font in available_fonts:
                        plt.rcParams['font.family'] = font
                        self.font_path = font # Store the found font name for textwrap
                        break
                else:
                    plt.rcParams['font.family'] = 'DejaVu Sans'
                    print("警告: 日本語フォントが見つかりませんでした。デフォルトフォントを使用します。")

            plt.rcParams['axes.unicode_minus'] = False # Enable minus sign in Japanese fonts
            print(f"matplotlib font set to: {plt.rcParams['font.family']}") # Debugging font setting

        except Exception as e:
            print(f"フォント設定エラー: {e}")
            plt.rcParams['font.family'] = 'DejaVu Sans'
            plt.rcParams['axes.unicode_minus'] = False

    def save_image(self, file_storage_object):
        """
        画像ファイルを専用ディレクトリに保存し、新しいファイル名を返す。
        file_storage_objectはFlaskのrequest.filesから来るもの。
        """
        if not file_storage_object:
            return None
        try:
            # FlaskのFileStorageオブジェクトからファイル名を抽出
            original_filename = file_storage_object.filename
            file_ext = os.path.splitext(original_filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            new_path = os.path.join(self.images_dir, unique_filename)

            # ファイルを保存
            file_storage_object.save(new_path)
            return unique_filename
        except Exception as e:
            print(f"画像保存エラー: {e}")
            return None

    def get_image_path(self, filename):
        """ファイル名から完全パスを取得"""
        if filename:
            return os.path.join(self.images_dir, filename)
        return None

    def load_image_as_base64(self, filename):
        """画像ファイルをBase64として読み込み（HTML出力用）"""
        try:
            image_path = self.get_image_path(filename)
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"画像読み込みエラー: {e}")
        return None

    def generate_id(self, entry_type):
        """IDとタイムスタンプの生成"""
        timestamp = datetime.now().isoformat(timespec='seconds').replace(':', '-') # Avoid colon in filename for safety
        return f"{entry_type}-{timestamp}"

    def generate_hash(self, data):
        """改ざん防止のためのハッシュ生成"""
        temp_data = data.copy()
        for key in ['today_completed_images', 'results_images', 'images', 'weekly_activity_images']:
            if key in temp_data and isinstance(temp_data[key], list):
                temp_data[key] = sorted(temp_data[key]) # Ensure consistent order for hashing
        data_str = json.dumps(temp_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def add_entry(self, entry_data):
        """エントリーの追加（最終保存）"""
        entry = {
            'id': self.generate_id(entry_data['type']),
            'type': entry_data['type'],
            'timestamp': datetime.now().isoformat(),
            'data': entry_data['data'],
            'hash': self.generate_hash(entry_data['data']),
            'status': 'completed'
        }
        self.entries.append(entry)

        # Corresponding draft should be removed if it exists
        if 'draft_id' in entry_data and entry_data['draft_id']:
            self.drafts = [d for d in self.drafts if d['id'] != entry_data['draft_id']]

        self.save_data()

    def update_entry(self, entry_id, new_entry_data):
        """既存のエントリーを更新"""
        for i, entry in enumerate(self.entries):
            if entry['id'] == entry_id:
                self.entries[i]['data'] = new_entry_data['data']
                self.entries[i]['hash'] = self.generate_hash(new_entry_data['data'])
                self.entries[i]['timestamp'] = datetime.now().isoformat()
                self.save_data()
                return True
        # Check drafts if it's a draft being updated to completed
        for i, draft in enumerate(self.drafts):
            if draft['id'] == entry_id:
                # Promote draft to completed entry
                self.drafts.pop(i) # Remove from drafts
                self.add_entry({'type': new_entry_data['type'], 'data': new_entry_data['data']})
                return True
        return False


    def save_draft(self, entry_data):
        """下書きの保存"""
        draft_id = entry_data.get('draft_id')
        if not draft_id:
            draft_id = self.generate_id(f"draft_{entry_data['type']}")

        draft = {
            'id': draft_id,
            'type': entry_data['type'],
            'timestamp': datetime.now().isoformat(),
            'data': entry_data['data'],
            'status': 'draft'
        }

        for i, d in enumerate(self.drafts):
            if d['id'] == draft_id:
                self.drafts[i] = draft
                break
        else:
            self.drafts.append(draft)
        self.save_drafts()
        return draft_id

    def delete_entry(self, entry_id):
        """エントリーを削除（完成、下書き両方から）"""
        original_len_entries = len(self.entries)
        self.entries = [entry for entry in self.entries if entry['id'] != entry_id]
        original_len_drafts = len(self.drafts)
        self.drafts = [draft for draft in self.drafts if draft['id'] != entry_id]

        if len(self.entries) < original_len_entries or len(self.drafts) < original_len_drafts:
            self.save_data()
            self.save_drafts()
            return True
        return False

    def get_entry_by_id(self, entry_id):
        """IDに基づいてエントリーまたは下書きを取得"""
        for entry in self.entries:
            if entry['id'] == entry_id:
                return entry
        for draft in self.drafts:
            if draft['id'] == entry_id:
                return draft
        return None

    def get_entry_title(self, entry):
        """エントリーのタイトルを取得"""
        if entry['type'] == 'daily':
            return f"日報 - {entry['data'].get('name', '無題')}"
        elif entry['type'] == 'experiment':
            return f"実験 - {entry['data'].get('purpose', '無題')[:30]}..."
        elif entry['type'] == 'participation':
            return f"参加報告 - {entry['data'].get('content', '無題')[:30]}..."
        elif entry['type'] == 'research_meeting':
            return f"研究会報告 - {entry['data'].get('meeting_title', '無題')}"
        return "不明"

    def get_all_entries_for_list(self):
        """表示用のエントリーと下書きの結合リストを返す"""
        combined = []
        for entry in self.entries:
            combined.append({
                'id': entry['id'],
                'type': entry['type'],
                'date': entry['timestamp'][:10],
                'title': self.get_entry_title(entry),
                'tags': entry['data'].get('tags', ''),
                'status': '完成'
            })
        for draft in self.drafts:
            combined.append({
                'id': draft['id'],
                'type': draft['type'],
                'date': draft['timestamp'][:10],
                'title': self.get_entry_title(draft) + " (下書き)",
                'tags': draft['data'].get('tags', ''),
                'status': '下書き'
            })
        combined.sort(key=lambda x: x['id'], reverse=True)
        return combined

    def get_all_images_for_selection(self):
        """画像選択用の全画像リストを返す"""
        image_list = []
        for entry in self.entries:
            if entry['type'] == 'daily' and entry['data'].get('today_completed_images'):
                for img_name in entry['data']['today_completed_images']:
                    image_list.append({'filename': img_name, 'source_type': 'daily', 'source_field': 'today_completed_images'})
            elif entry['type'] == 'experiment' and entry['data'].get('results_images'):
                for img_name in entry['data']['results_images']:
                    image_list.append({'filename': img_name, 'source_type': 'experiment', 'source_field': 'results_images'})
        return image_list


    def save_data(self):
        """完成エントリーをJSONに保存"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)
        self.save_html() # Always generate HTML on data save

    def save_drafts(self):
        """下書きをJSONに保存"""
        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(self.drafts, f, ensure_ascii=False, indent=2)

    def load_data(self):
        """JSONからデータを読み込み"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.entries = json.load(f)
            if os.path.exists(self.draft_file):
                with open(self.draft_file, 'r', encoding='utf-8') as f:
                    self.drafts = json.load(f)
        except Exception as e:
            print(f"データの読み込みに失敗しました: {str(e)}")
            self.entries = []
            self.drafts = []

    def save_html(self):
        """HTMLファイルの保存"""
        html_content = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>研究記録</title>
            <style>
                body { font-family: 'MS Gothic', 'Meiryo', sans-serif; margin: 20px; line-height: 1.6; }
                h1, h2 { color: #333; }
                .entry { border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
                .entry-header { background: #f0f0f0; padding: 10px; margin: -20px -20px 20px -20px; border-radius: 8px 8px 0 0; }
                .field { margin: 10px 0; }
                .label { font-weight: bold; color: #555; }
                pre { background: #eee; padding: 10px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; }
                .images { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
                .images img { max-width: 200px; height: auto; border: 1px solid #ccc; border-radius: 4px; }
                .tags { color: #007bff; background: #e0f0ff; padding: 3px 8px; border-radius: 12px; font-size: 0.9em; }
                .draft { background-color: #fff3cd; border-color: #ffc107; }
                .draft .entry-header { background-color: #ffeeba; }
            </style>
        </head>
        <body>
            <h1>研究記録データ</h1>
        """

        all_records = sorted(self.entries + self.drafts, key=lambda x: x['timestamp'], reverse=True)

        for record in all_records:
            html_content += f"""
            <div class="entry {'draft' if record.get('status') == 'draft' else ''}">
                <div class="entry-header">
                    <h2>{self.get_entry_title(record)} {'(下書き)' if record.get('status') == 'draft' else ''}</h2>
                    <p>ID: {record['id']}</p>
                    <p>作成日時: {record['timestamp']}</p>
                    <p>状態: {'完成' if record.get('status') == 'completed' else '下書き'}</p>
                    {f"<p>ハッシュ: {record['hash'][:16]}...</p>" if 'hash' in record else ''}
                </div>
            """

            if record['type'] == 'daily':
                html_content += self._format_daily_html(record['data'])
            elif record['type'] == 'experiment':
                html_content += self._format_experiment_html(record['data'])
            elif record['type'] == 'participation':
                html_content += self._format_participation_html(record['data'])
            elif record['type'] == 'research_meeting':
                html_content += self._format_research_meeting_html(record['data'])

            html_content += "</div>"

        html_content += """
        </body>
        </html>
        """

        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _format_daily_html(self, data):
        html = f"""
        <div class="field"><span class="label">日付:</span> {data.get('date', '')}</div>
        <div class="field"><span class="label">勤務形態:</span> {data.get('work_type', '')}</div>
        <div class="field"><span class="label">来た時間:</span> {data.get('arrival_time', '')}</div>
        <div class="field"><span class="label">帰る時間:</span> {data.get('departure_time', '')}</div>
        <div class="field"><span class="label">名前:</span> {data.get('name', '')}</div>
        <div class="field"><span class="label">今日の目標:</span> <pre>{data.get('today_goal', '')}</pre></div>
        <div class="field"><span class="label">今日のTODO:</span> <pre>{data.get('today_todo', '')}</pre></div>
        <div class="field"><span class="label">今日できたこと:</span> <pre>{data.get('today_completed', '')}</pre></div>
        """
        if data.get('today_completed_images'):
            html += '<div class="field"><span class="label">今日できたこと（画像）:</span><div class="images">'
            for filename in data['today_completed_images']:
                base64_data = self.load_image_as_base64(filename)
                if base64_data:
                    html += f'<img src="data:image/jpeg;base64,{base64_data}" alt="{filename}">'
            html += '</div></div>'
        html += f"""
        <div class="field"><span class="label">今日できなかったこととその理由:</span> <pre>{data.get('today_incomplete_reason', '')}</pre></div>
        <div class="field"><span class="label">明日のTODO:</span> <pre>{data.get('tomorrow_todo', '')}</pre></div>
        <div class="field"><span class="label">タグ:</span> <span class="tags">{data.get('tags', '')}</span></div>
        """
        return html

    def _format_experiment_html(self, data):
        html = f"""
        <div class="field"><span class="label">実験日:</span> {data.get('experiment_date', '')}</div>
        <div class="field"><span class="label">目的:</span> <pre>{data.get('purpose', '')}</pre></div>
        <div class="field"><span class="label">仮説:</span> <pre>{data.get('hypothesis', '')}</pre></div>
        <div class="field"><span class="label">手法:</span> <pre>{data.get('method', '')}</pre></div>
        <div class="field"><span class="label">評価方法:</span> <pre>{data.get('evaluation', '')}</pre></div>
        <div class="field"><span class="label">結果:</span> <pre>{data.get('results', '')}</pre></div>
        """
        if data.get('results_images'):
            html += '<div class="field"><span class="label">結果（画像）:</span><div class="images">'
            for filename in data['results_images']:
                base64_data = self.load_image_as_base64(filename)
                if base64_data:
                    html += f'<img src="data:image/jpeg;base64,{base64_data}" alt="{filename}">'
            html += '</div></div>'
        html += f"""
        <div class="field"><span class="label">評価:</span> <pre>{data.get('assessment', '')}</pre></div>
        <div class="field"><span class="label">考察:</span> <pre>{data.get('consideration', '')}</pre></div>
        <div class="field"><span class="label">コード:</span> <pre>{data.get('code', '')}</pre></div>
        <div class="field"><span class="label">Tips:</span> <pre>{data.get('tips', '')}</pre></div>
        <div class="field"><span class="label">タグ:</span> <span class="tags">{data.get('tags', '')}</span></div>
        """
        return html

    def _format_participation_html(self, data):
        html = f"""
        <div class="field"><span class="label">内容:</span> <pre>{data.get('content', '')}</pre></div>
        """
        if data.get('images'):
            html += '<div class="field"><span class="label">画像:</span><div class="images">'
            for filename in data['images']:
                base64_data = self.load_image_as_base64(filename)
                if base64_data:
                    html += f'<img src="data:image/jpeg;base64,{base64_data}" alt="{filename}">'
            html += '</div></div>'
        html += f'<div class="field"><span class="label">タグ:</span> <span class="tags">{data.get("tags", "")}</span></div>'
        return html

    def _format_research_meeting_html(self, data):
        html = f"""
        <div class="field"><span class="label">研究会タイトル:</span> {data.get('meeting_title', '')}</div>
        <div class="field"><span class="label">現在の状況:</span> <pre>{data.get('current_status', '')}</pre></div>
        <div class="field"><span class="label">今週行ったこととそれに対する考え:</span> <pre>{data.get('weekly_activities_thoughts', '')}</pre></div>
        """
        if data.get('weekly_activity_images'):
            html += '<div class="field"><span class="label">今週行ったことの画像:</span><div class="images">'
            for filename in data['weekly_activity_images']:
                base64_data = self.load_image_as_base64(filename)
                if base64_data:
                    html += f'<img src="data:image/jpeg;base64,{base64_data}" alt="{filename}">'
            html += '</div></div>'
        html += f"""
        <div class="field"><span class="label">アドバイスがほしいこと:</span> <pre>{data.get('advice_needed', '')}</pre></div>
        <div class="field"><span class="label">来週取り組むこと:</span> <pre>{data.get('next_week_tasks', '')}</pre></div>
        <div class="field"><span class="label">タグ:</span> <span class="tags">{data.get('tags', '')}</span></div>
        """
        return html

    def _create_pdf_png_output(self, entry, output_filename, output_format):
        """PDF/PNG出力の共通ロジック"""
        try:
            if self.font_path and os.path.exists(self.font_path):
                font_prop = fm.FontProperties(fname=self.font_path)
            else:
                font_prop = fm.FontProperties(family='DejaVu Sans') # Fallback
                print("警告: PDF/PNG出力用の日本語フォントパスが見つかりません。DejaVu Sansを使用します。")

            # A4サイズ設定 (縦横切り替え)
            if entry['type'] in ['daily', 'research_meeting']:
                fig, ax = plt.subplots(figsize=(11.69, 8.27)) # A4横
            else:
                fig, ax = plt.subplots(figsize=(8.27, 11.69)) # A4縦

            if entry['type'] == 'daily':
                self._format_daily_pdf(entry, ax, font_prop)
            elif entry['type'] == 'experiment':
                self._format_experiment_pdf(entry, ax, font_prop)
            elif entry['type'] == 'participation':
                self._format_participation_pdf(entry, ax, font_prop)
            elif entry['type'] == 'research_meeting':
                self._format_research_meeting_pdf(entry, ax, font_prop)

            ax.axis('off')
            plt.tight_layout()
            plt.savefig(output_filename, format=output_format, bbox_inches='tight', dpi=300)
            plt.close()
            return True
        except Exception as e:
            print(f"PDF/PNG作成エラー: {e}")
            return False

    def export_to_pdf_logic(self, entry, filename):
        """単一エントリーのPDF出力ロジック"""
        return self._create_pdf_png_output(entry, filename, 'pdf')

    def export_to_png_logic(self, entry, filename):
        """単一エントリーのPNG出力ロジック"""
        return self._create_pdf_png_output(entry, filename, 'png')

    def _format_daily_pdf(self, entry, ax, font_prop):
        """日報のPDFフォーマット (共通)"""
        data = entry['data']
        y_pos = 0.95
        ax.text(0.5, y_pos, "日々の記録", fontsize=16, fontweight='bold', ha='center', transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.08
        ax.text(0.05, y_pos, f"日付: {data.get('date', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
        ax.text(0.25, y_pos, f"勤務形態: {data.get('work_type', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
        if data.get('work_type') == '登校':
            ax.text(0.45, y_pos, f"来た時間: {data.get('arrival_time', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
            ax.text(0.65, y_pos, f"帰る時間: {data.get('departure_time', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.04
        ax.text(0.05, y_pos, f"名前: {data.get('name', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.06

        fields = [
            ('今日の目標', data.get('today_goal', '')),
            ('今日のTODO', data.get('today_todo', '')),
            ('今日できたこと', data.get('today_completed', '')),
            ('今日できなかったこととその理由', data.get('today_incomplete_reason', '')),
            ('明日のTODO', data.get('tomorrow_todo', ''))
        ]
        for label, content in fields:
            ax.text(0.05, y_pos, f"{label}:", fontsize=10, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
            y_pos -= 0.04
            lines = textwrap.wrap(content, width=80)
            for line in lines[:3]:
                ax.text(0.05, y_pos, line, fontsize=9, transform=ax.transAxes, fontproperties=font_prop)
                y_pos -= 0.03
            if label == '今日できたこと' and data.get('today_completed_images') and y_pos > 0.15:
                ax.text(0.05, y_pos, "画像:", fontsize=9, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
                y_pos -= 0.03
                for i, filename in enumerate(data['today_completed_images'][:2]):
                    img_path = self.get_image_path(filename)
                    if img_path and os.path.exists(img_path):
                        try:
                            img = Image.open(img_path)
                            img_width, img_height = img.size
                            aspect_ratio = img_height / img_width
                            display_width = 0.2
                            display_height = display_width * aspect_ratio * (ax.get_xlim()[1] - ax.get_xlim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0])
                            img_x = 0.05 + i * 0.25
                            img_y = y_pos - display_height - 0.01
                            ax.imshow(img, extent=[img_x, img_x + display_width, img_y, img_y + display_height], transform=ax.transAxes, aspect='auto')
                            y_pos -= (display_height + 0.01) if i == 0 else 0 # Adjust y_pos only after first image, if multiple
                        except Exception as img_e:
                            ax.text(0.05, y_pos, f"画像表示エラー: {os.path.basename(img_path)} ({img_e})", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                            y_pos -= 0.025
                    else:
                        ax.text(0.05, y_pos, f"画像が見つかりません: {os.path.basename(img_path)}", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                        y_pos -= 0.025
                y_pos -= 0.02
            y_pos -= 0.02
        if data.get('tags'):
            ax.text(0.05, y_pos, f"タグ: {data.get('tags', '')}", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)

    def _format_experiment_pdf(self, entry, ax, font_prop):
        """実験計画書のPDFフォーマット (共通)"""
        data = entry['data']
        y_pos = 0.95
        ax.text(0.5, y_pos, "実験計画書", fontsize=16, fontweight='bold', ha='center', transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.08
        ax.text(0.05, y_pos, f"実験日: {data.get('experiment_date', '')}", fontsize=12, transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.06

        fields = [
            ('目的', data.get('purpose', '')), ('仮説', data.get('hypothesis', '')), ('手法', data.get('method', '')),
            ('評価方法', data.get('evaluation', '')), ('結果', data.get('results', '')), ('評価', data.get('assessment', '')),
            ('考察', data.get('consideration', '')), ('コード', data.get('code', '')), ('Tips', data.get('tips', ''))
        ]
        for label, content in fields:
            if y_pos < 0.1: break
            ax.text(0.05, y_pos, f"{label}:", fontsize=10, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
            y_pos -= 0.04
            lines = textwrap.wrap(content, width=60)
            for line in lines[:5]:
                ax.text(0.05, y_pos, line, fontsize=9, transform=ax.transAxes, fontproperties=font_prop)
                y_pos -= 0.03
            if label == '結果' and data.get('results_images') and y_pos > 0.15:
                ax.text(0.05, y_pos, "画像:", fontsize=9, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
                y_pos -= 0.03
                for i, filename in enumerate(data['results_images'][:3]):
                    img_path = self.get_image_path(filename)
                    if img_path and os.path.exists(img_path):
                        try:
                            img = Image.open(img_path)
                            img_width, img_height = img.size
                            aspect_ratio = img_height / img_width
                            display_width = 0.2
                            display_height = display_width * aspect_ratio * (ax.get_xlim()[1] - ax.get_xlim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0])
                            img_x = 0.05 + i * 0.25
                            img_y = y_pos - display_height - 0.01
                            ax.imshow(img, extent=[img_x, img_x + display_width, img_y, img_y + display_height], transform=ax.transAxes, aspect='auto')
                            y_pos -= (display_height + 0.01) if i == 0 else 0
                        except Exception as img_e:
                            ax.text(0.05, y_pos, f"画像表示エラー: {os.path.basename(img_path)} ({img_e})", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                            y_pos -= 0.025
                    else:
                        ax.text(0.05, y_pos, f"画像が見つかりません: {os.path.basename(img_path)}", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                        y_pos -= 0.025
                y_pos -= 0.02
            y_pos -= 0.02
        if data.get('tags'):
            ax.text(0.05, y_pos, f"タグ: {data.get('tags', '')}", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)


    def _format_participation_pdf(self, entry, ax, font_prop):
        """参加報告書のPDFフォーマット (共通)"""
        data = entry['data']
        y_pos = 0.95
        ax.text(0.5, y_pos, "参加報告書", fontsize=16, fontweight='bold', ha='center', transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.08
        ax.text(0.05, y_pos, "内容:", fontsize=10, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.04
        lines = textwrap.wrap(data.get('content', ''), width=60)
        for line in lines[:20]:
            ax.text(0.05, y_pos, line, fontsize=9, transform=ax.transAxes, fontproperties=font_prop)
            y_pos -= 0.03
            if y_pos < 0.1: break

        if data.get('images') and y_pos > 0.15:
            y_pos -= 0.02
            ax.text(0.05, y_pos, "画像:", fontsize=10, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
            y_pos -= 0.03
            for i, filename in enumerate(data['images'][:5]):
                img_path = self.get_image_path(filename)
                if img_path and os.path.exists(img_path):
                    try:
                        img = Image.open(img_path)
                        img_width, img_height = img.size
                        aspect_ratio = img_height / img_width
                        display_width = 0.2
                        display_height = display_width * aspect_ratio * (ax.get_xlim()[1] - ax.get_xlim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0])
                        img_x = 0.05 + i * 0.25
                        img_y = y_pos - display_height - 0.01
                        ax.imshow(img, extent=[img_x, img_x + display_width, img_y, img_y + display_height], transform=ax.transAxes, aspect='auto')
                        y_pos -= (display_height + 0.01) if i == 0 else 0
                    except Exception as img_e:
                        ax.text(0.05, y_pos, f"画像表示エラー: {os.path.basename(img_path)} ({img_e})", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                        y_pos -= 0.025
                else:
                    ax.text(0.05, y_pos, f"画像が見つかりません: {os.path.basename(img_path)}", fontsize=8, transform=ax.transAxes, fontproperties=font_prop)
                    y_pos -= 0.025
        if data.get('tags'):
            ax.text(0.05, y_pos, f"タグ: {data.get('tags', '')}", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)


    def _format_research_meeting_pdf(self, entry, ax, font_prop):
        """研究会報告書のPDFフォーマット (A4横向けスライド風)"""
        data = entry['data']
        y_pos = 0.9
        x_start = 0.05

        ax.text(0.5, y_pos, data.get('meeting_title', '研究会報告'), fontsize=20, fontweight='bold', ha='center', transform=ax.transAxes, fontproperties=font_prop)
        y_pos -= 0.12

        sections = [
            ('現在の状況', 'current_status', 80, 3, 14, 12),
            ('今週行ったこととそれに対する考え', 'weekly_activities_thoughts', 80, 3, 14, 12),
            ('アドバイスがほしいこと', 'advice_needed', 80, 3, 14, 12),
            ('来週取り組むこと', 'next_week_tasks', 80, 3, 14, 12)
        ]

        for label, key, wrap_width, max_lines, title_fs, content_fs in sections:
            if y_pos < 0.15: # ページ下部に近づいたら停止
                break
            ax.text(x_start, y_pos, f"【{label}】", fontsize=title_fs, fontweight='bold', transform=ax.transAxes, fontproperties=font_prop)
            y_pos -= 0.04

            lines = textwrap.wrap(data.get(key, ''), width=wrap_width)
            for line in lines[:max_lines]:
                ax.text(x_start + 0.02, y_pos, line, fontsize=content_fs, transform=ax.transAxes, fontproperties=font_prop)
                y_pos -= 0.035
            y_pos -= 0.01

            # 画像表示
            if key == 'weekly_activities_thoughts' and data.get('weekly_activity_images'):
                current_image_x_offset = 0
                image_start_y = y_pos
                num_images_shown = 0
                for i, filename in enumerate(data['weekly_activity_images'][:2]): # 最大2つまで表示
                    if current_image_x_offset + 0.25 > 1.0 - x_start: # 画面幅を超えそうなら改行
                        break
                    img_path = self.get_image_path(filename)
                    if img_path and os.path.exists(img_path):
                        try:
                            img = Image.open(img_path)
                            img_width, img_height = img.size
                            aspect_ratio = img_height / img_width
                            display_width = 0.25 # スライドの画像は少し大きめに
                            display_height = display_width * aspect_ratio * (ax.get_xlim()[1] - ax.get_xlim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0])
                            
                            img_x = x_start + current_image_x_offset
                            img_y = image_start_y - display_height - 0.01
                            
                            ax.imshow(img, extent=[img_x, img_x + display_width, img_y, img_y + display_height], transform=ax.transAxes, aspect='auto')
                            current_image_x_offset += (display_width + 0.05)
                            num_images_shown += 1
                        except Exception as img_e:
                            ax.text(x_start + current_image_x_offset, image_start_y - 0.03, f"画像エラー: {os.path.basename(img_path)} ({img_e})", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)
                            current_image_x_offset += 0.2
                    else:
                        ax.text(x_start + current_image_x_offset, image_start_y - 0.03, f"画像なし: {os.path.basename(filename)}", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)
                        current_image_x_offset += 0.2
                if num_images_shown > 0:
                    y_pos = image_start_y - display_height - 0.02 # 画像の下にy_posを移動

            y_pos -= 0.02 # 各セクション間の間隔

        if data.get('tags'):
            ax.text(x_start, 0.05, f"タグ: {data.get('tags', '')}", fontsize=10, transform=ax.transAxes, fontproperties=font_prop)


# --- Flask App Setup ---
app = Flask(__name__)
# Get the directory of the current script (app.py)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Initialize our core logic, passing the script directory
core_app = ResearchDiaryCore(script_dir)

# --- Routes ---

@app.route('/')
def index():
    """メイン画面: エントリーリストを表示"""
    entries_for_display = core_app.get_all_entries_for_list()
    return render_template('index.html', entries=entries_for_display)

@app.route('/create/<entry_type>', methods=['GET', 'POST'])
def create_entry(entry_type):
    """
    新しいエントリーを作成するフォームを表示し、データを受け取る
    entry_type: daily, experiment, participation, research_meeting
    """
    current_data = {}
    draft_id = None
    all_images_for_selection = []

    if entry_type == 'research_meeting':
        all_images_for_selection = core_app.get_all_images_for_selection()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        images_to_save = {}

        # Handle image uploads for daily/experiment/participation
        if entry_type == 'daily':
            if 'today_completed_images_upload' in request.files:
                uploaded_files = request.files.getlist('today_completed_images_upload')
                saved_filenames = []
                for file in uploaded_files:
                    if file.filename != '':
                        saved_name = core_app.save_image(file)
                        if saved_name:
                            saved_filenames.append(saved_name)
                form_data['today_completed_images'] = saved_filenames

            # Handle existing images passed from form (for drafts/edits)
            existing_images = request.form.getlist('today_completed_images_existing')
            if existing_images:
                if 'today_completed_images' in form_data:
                    form_data['today_completed_images'].extend(existing_images)
                else:
                    form_data['today_completed_images'] = existing_images

        elif entry_type == 'experiment':
            if 'results_images_upload' in request.files:
                uploaded_files = request.files.getlist('results_images_upload')
                saved_filenames = []
                for file in uploaded_files:
                    if file.filename != '':
                        saved_name = core_app.save_image(file)
                        if saved_name:
                            saved_filenames.append(saved_name)
                form_data['results_images'] = saved_filenames

            existing_images = request.form.getlist('results_images_existing')
            if existing_images:
                if 'results_images' in form_data:
                    form_data['results_images'].extend(existing_images)
                else:
                    form_data['results_images'] = existing_images

        elif entry_type == 'participation':
            if 'images_upload' in request.files:
                uploaded_files = request.files.getlist('images_upload')
                saved_filenames = []
                for file in uploaded_files:
                    if file.filename != '':
                        saved_name = core_app.save_image(file)
                        if saved_name:
                            saved_filenames.append(saved_name)
                form_data['images'] = saved_filenames

            existing_images = request.form.getlist('images_existing')
            if existing_images:
                if 'images' in form_data:
                    form_data['images'].extend(existing_images)
                else:
                    form_data['images'] = existing_images

        elif entry_type == 'research_meeting':
            # Research meeting images are only referenced (no direct upload in this form)
            referenced_images = request.form.getlist('weekly_activity_images_referenced')
            form_data['weekly_activity_images'] = referenced_images


        # Determine if it's a save or a draft
        if 'save_button' in request.form:
            core_app.add_entry({'type': entry_type, 'data': form_data})
            return redirect(url_for('index'))
        elif 'draft_button' in request.form:
            draft_id = core_app.save_draft({'type': entry_type, 'data': form_data})
            return redirect(url_for('edit_entry', entry_id=draft_id)) # Redirect back to the draft for continuous editing

    # GET request or initial form display
    template_map = {
        'daily': 'daily_record_form.html',
        'experiment': 'experiment_plan_form.html',
        'participation': 'participation_report_form.html',
        'research_meeting': 'research_meeting_report_form.html'
    }
    return render_template(template_map.get(entry_type, 'index.html'),
                           data=current_data,
                           draft_id=draft_id,
                           all_images_for_selection=json.dumps(all_images_for_selection), # Pass as JSON string
                           datetime=datetime)


@app.route('/edit/<entry_id>', methods=['GET', 'POST'])
def edit_entry(entry_id):
    """
    既存のエントリーまたは下書きを編集するフォームを表示し、データを受け取る
    """
    entry = core_app.get_entry_by_id(entry_id)
    if not entry:
        return "エントリーが見つかりません", 404

    current_data = entry['data']
    entry_type = entry['type']
    is_draft = entry.get('status') == 'draft'
    all_images_for_selection = []

    if entry_type == 'research_meeting':
        all_images_for_selection = core_app.get_all_images_for_selection()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        
        # Handle image uploads/updates (similar to create_entry)
        if entry_type == 'daily':
            # Existing images from the form (already saved filenames)
            existing_images = request.form.getlist('today_completed_images_existing')
            # New uploads
            uploaded_files = request.files.getlist('today_completed_images_upload')
            saved_filenames = []
            for file in uploaded_files:
                if file.filename != '':
                    saved_name = core_app.save_image(file)
                    if saved_name:
                        saved_filenames.append(saved_name)
            form_data['today_completed_images'] = existing_images + saved_filenames

        elif entry_type == 'experiment':
            existing_images = request.form.getlist('results_images_existing')
            uploaded_files = request.files.getlist('results_images_upload')
            saved_filenames = []
            for file in uploaded_files:
                if file.filename != '':
                    saved_name = core_app.save_image(file)
                    if saved_name:
                        saved_filenames.append(saved_name)
            form_data['results_images'] = existing_images + saved_filenames

        elif entry_type == 'participation':
            existing_images = request.form.getlist('images_existing')
            uploaded_files = request.files.getlist('images_upload')
            saved_filenames = []
            for file in uploaded_files:
                if file.filename != '':
                    saved_name = core_app.save_image(file)
                    if saved_name:
                        saved_filenames.append(saved_name)
            form_data['images'] = existing_images + saved_filenames

        elif entry_type == 'research_meeting':
            referenced_images = request.form.getlist('weekly_activity_images_referenced')
            form_data['weekly_activity_images'] = referenced_images


        if 'save_button' in request.form:
            # If it was a draft, promote to completed. If completed, just update.
            core_app.update_entry(entry_id, {'type': entry_type, 'data': form_data})
            return redirect(url_for('index'))
        elif 'draft_button' in request.form:
            # Update the existing draft or save as a new draft if it was a completed entry being edited
            core_app.save_draft({'type': entry_type, 'data': form_data, 'draft_id': entry_id if is_draft else None})
            return redirect(url_for('edit_entry', entry_id=entry_id)) # Keep editing the same ID
    
    # GET request to display form with current data
    template_map = {
        'daily': 'daily_record_form.html',
        'experiment': 'experiment_plan_form.html',
        'participation': 'participation_report_form.html',
        'research_meeting': 'research_meeting_report_form.html'
    }
    return render_template(template_map.get(entry_type, 'index.html'),
                           data=current_data,
                           entry_id=entry_id, # Pass entry_id for edit mode
                           is_draft=is_draft,
                           all_images_for_selection=json.dumps(all_images_for_selection), # Pass as JSON string
                           datetime=datetime)


@app.route('/view/<entry_id>')
def view_entry(entry_id):
    """単一のエントリーを表示"""
    entry = core_app.get_entry_by_id(entry_id)
    if not entry:
        return "エントリーが見つかりません", 404
    return render_template('view_entry.html', entry=entry, core_app=core_app)


@app.route('/delete/<entry_id>')
def delete_entry(entry_id):
    """エントリーの削除"""
    if core_app.delete_entry(entry_id):
        return redirect(url_for('index'))
    return "削除に失敗しました", 500

@app.route('/export_pdf/<entry_id>')
def export_pdf(entry_id):
    """PDFをエクスポートしてダウンロード"""
    entry = core_app.get_entry_by_id(entry_id)
    if not entry:
        return "エントリーが見つかりません", 404

    temp_dir = tempfile.gettempdir()
    temp_pdf_path = os.path.join(temp_dir, f"{entry_id}.pdf")

    if core_app.export_to_pdf_logic(entry, temp_pdf_path):
        return send_file(temp_pdf_path, as_attachment=True, download_name=f"{core_app.get_entry_title(entry).replace(' ', '_').replace('/', '-')}.pdf")
    return "PDF生成に失敗しました", 500

@app.route('/export_png/<entry_id>')
def export_png(entry_id):
    """PNGをエクスポートしてダウンロード"""
    entry = core_app.get_entry_by_id(entry_id)
    if not entry:
        return "エントリーが見つかりません", 404

    temp_dir = tempfile.gettempdir()
    temp_png_path = os.path.join(temp_dir, f"{entry_id}.png")

    if core_app.export_to_png_logic(entry, temp_png_path):
        return send_file(temp_png_path, as_attachment=True, download_name=f"{core_app.get_entry_title(entry).replace(' ', '_').replace('/', '-')}.png")
    return "PNG生成に失敗しました", 500

@app.route('/images/<filename>')
def serve_image(filename):
    """画像をWeb経由で提供するためのルート"""
    return send_file(core_app.get_image_path(filename), mimetype='image/jpeg')

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', 'localhost')
    port = os.environ.get('FLASK_RUN_PORT', '5000')
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        def open_browser():
            time.sleep(2)
            print(f"ブラウザを自動起動中: http://{host}:{port}")
            webbrowser.open_new_tab(f"http://{host}:{port}")

        threading.Timer(1, open_browser).start()

    app.run(debug=True)