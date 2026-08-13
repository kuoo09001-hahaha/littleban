# 在 core/asr.py 中添加这个方法

from funasr import AutoModel
import os


class EmotionRecognizer:
    """情绪识别器"""
    
    def __init__(self):
        """初始化情绪识别模型"""
        print("正在加载情绪识别模型...")
        self.model = AutoModel(model="iic/emotion2vec_base")
        print("情绪识别模型加载完成")
    
    def recognize(self, audio_path):
        """
        识别音频情绪
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 情绪识别结果
        """
        if not os.path.exists(audio_path):
            return {"error": f"音频文件不存在: {audio_path}"}
        
        try:
            result = self.model.generate(audio_path)
            
            # 解析结果
            if result and len(result) > 0:
                if isinstance(result[0], dict):
                    return {
                        "emotion": result[0].get('emotion', 'unknown'),
                        "confidence": float(result[0].get('confidence', 0)),
                        "success": True
                    }
                else:
                    return {
                        "raw_result": str(result),
                        "success": True
                    }
            else:
                return {
                    "emotion": "unknown",
                    "confidence": 0,
                    "success": False,
                    "message": "未识别出情绪"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# 使用示例
if __name__ == "__main__":
    # 测试情绪识别
    audio_path = 'C:/Users/DELL/.cache/modelscope/hub/models/iic/emotion2vec_base/example/test.wav'
    recognizer = EmotionRecognizer()
    result = recognizer.recognize(audio_path)
    print(result)