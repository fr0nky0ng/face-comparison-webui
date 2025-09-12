import gradio as gr
import subprocess
import os
import shutil
from datetime import datetime
import time

# --- 配置 ---
CONDA_ENV_NAME = 'face-compare'
COMPARE_FACES_SCRIPT_NAME = 'compare_faces.py'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(SCRIPT_DIR, 'upload')

# --- 初始化设置 ---
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 辅助函数 ---


def get_history_images():
    """扫描并返回排序后的历史图片列表。"""
    try:
        all_files = [os.path.join(UPLOAD_DIR, f)
                     for f in os.listdir(UPLOAD_DIR)]
        image_files = [f for f in all_files if os.path.isfile(
            f) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return image_files
    except Exception as e:
        print(f"读取历史目录时出错: {e}")
        return []


def clear_history():
    """清除所有上传的图片。"""
    count = 0
    try:
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
                count += 1
        # 使用 gr.Info() 弹出提示消息
        gr.Info(f"成功删除 {count} 个历史文件。")
        return []  # 返回空列表以更新图库
    except Exception as e:
        gr.Error(f"清除历史文件时发生错误: {e}")
        return get_history_images()


def run_comparison_script(image_one_path, image_two_path):
    """执行conda命令的核心函数。"""
    if not image_one_path or not image_two_path:
        return "错误: 一个或两个图片路径缺失。"
    local_script_path = os.path.join(SCRIPT_DIR, COMPARE_FACES_SCRIPT_NAME)
    command_to_run = ['python', local_script_path] if os.path.exists(
        local_script_path) else [COMPARE_FACES_SCRIPT_NAME]

    try:
        command = ['conda', 'run', '--no-capture-output', '-n', CONDA_ENV_NAME] + \
            command_to_run + ['--image-one', image_one_path,
                              '--image-two', image_two_path]
        print(f"正在执行命令: {' '.join(command)}")
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        return result.stdout
    except Exception as e:
        return f"命令执行时发生未知错误:\n{e}"


def save_and_run_comparison(img1_temp_path, img2_temp_path):
    """处理新上传，保存它们，运行比对，并更新历史记录。"""
    if img1_temp_path is None or img2_temp_path is None:
        return "错误: 请提供两张图片进行比对。", get_history_images()
    final_paths = []
    for temp_path in [img1_temp_path, img2_temp_path]:
        if UPLOAD_DIR not in os.path.abspath(temp_path):
            original_extension = os.path.splitext(
                os.path.basename(temp_path))[1]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            final_path = os.path.join(
                UPLOAD_DIR, f"{timestamp}{original_extension}")
            shutil.copy(temp_path, final_path)
            final_paths.append(final_path)
        else:
            final_paths.append(temp_path)
    output = run_comparison_script(final_paths[0], final_paths[1])
    return output, get_history_images()


def select_history_image(evt: gr.SelectData):
    """当用户在图库中点击一张图片时触发。"""
    return evt.value['image']['path']

# --- 最终修正：将操作拆分为独立的函数 ---


def update_image_component(selected_path):
    """第一步：只负责更新一个Image组件的值。"""
    if not selected_path:
        return gr.update()
    return gr.update(value=selected_path)


def switch_to_check_tab():
    """第二步：只负责切换到Check标签页。"""
    return gr.Tabs(selected=0)
# --- 修正结束 ---


# --- Gradio UI 定义 ---
with gr.Blocks(title="Face Comparison Tool") as demo:
    selected_history_image_path = gr.State()

    with gr.Tabs() as tabs:
        with gr.TabItem("Check", id=0):
            gr.Markdown("## 1. Upload Images or Select from History")
            gr.Markdown(
                "Upload two new images or go to the 'History' tab to select previously uploaded images.")
            with gr.Row():
                img1 = gr.Image(type="filepath", label="Image One")
                img2 = gr.Image(type="filepath", label="Image Two")
            gr.Markdown("## 2. Run Comparison")
            compare_btn = gr.Button("Compare", variant="primary")
            gr.Markdown("## 3. Output")
            output_text = gr.Textbox(
                label="Output Result", lines=10, interactive=False)

        with gr.TabItem("History", id=1):
            gr.Markdown("## Image History")
            gr.Markdown(
                "Images are sorted from newest to oldest. Click on an image to select it, then choose an action below.")
            with gr.Row():
                use_as_one_btn = gr.Button("Use Selected as Image One")
                use_as_two_btn = gr.Button("Use Selected as Image Two")
                refresh_btn = gr.Button("Refresh History")
            with gr.Row():
                clear_history_btn = gr.Button(
                    "Clear History (Deletes all uploaded images)", variant="stop")

            history_gallery = gr.Gallery(
                value=get_history_images,
                label="Uploaded Images", show_label=False, columns=8,
                object_fit="contain", height="auto", interactive=True
            )

    # --- 事件处理器 ---
    compare_btn.click(fn=save_and_run_comparison, inputs=[
                      img1, img2], outputs=[output_text, history_gallery])
    history_gallery.select(fn=select_history_image, inputs=None, outputs=[
                           selected_history_image_path], show_progress="hidden")
    refresh_btn.click(fn=get_history_images, inputs=None,
                      outputs=history_gallery)
    clear_history_btn.click(fn=clear_history, inputs=None,
                            outputs=[history_gallery])

    # --- 最终修正：使用 .then() 链式调用 ---
    # 处理 "Use as Image One" 按钮
    use_as_one_btn.click(
        fn=update_image_component,
        inputs=[selected_history_image_path],
        outputs=[img1]
    ).then(
        fn=switch_to_check_tab,
        inputs=None,
        outputs=[tabs]
    )

    # 处理 "Use as Image Two" 按钮
    use_as_two_btn.click(
        fn=update_image_component,
        inputs=[selected_history_image_path],
        outputs=[img2]
    ).then(
        fn=switch_to_check_tab,
        inputs=None,
        outputs=[tabs]
    )
    # --- 修正结束 ---

# --- 启动 Web 服务 ---
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")
