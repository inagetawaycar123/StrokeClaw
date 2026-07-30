import nibabel as nib
import numpy as np
from PIL import Image
import os


class ImagePreprocessor:
    def __init__(self, image_path):
        """
        初始化图像预处理器
        Args:
            image_path: nii.gz 格式文件路径
        """
        self.image_path = image_path
        self.image_data = None
        self.affine = None

    def load_image(self):
        """
        加载 nii.gz 格式文件
        Returns:
            bool: 加载是否成功
        """
        try:
            # 加载 nii.gz 文件
            nii_image = nib.load(self.image_path)
            self.image_data = nii_image.get_fdata()
            self.affine = nii_image.affine
            print(f"成功加载文件: {self.image_path}")
            print(f"图像形状: {self.image_data.shape}")
            return True
        except Exception as e:
            print(f"加载文件失败: {e}")
            return False

    def get_slice(self, slice_index, axis=2):
        """
        获取指定位置的切片
        Args:
            slice_index: 切片索引
            axis: 切片轴 (0, 1, 2)
        Returns:
            np.ndarray: 切片数据
        """
        if self.image_data is None:
            print("请先加载图像")
            return None

        # 检查切片索引是否有效
        if slice_index < 0 or slice_index >= self.image_data.shape[axis]:
            print(f"切片索引超出范围，有效范围: 0-{self.image_data.shape[axis] - 1}")
            return None

        # 获取切片
        if axis == 0:
            slice_data = self.image_data[slice_index, :, :]
        elif axis == 1:
            slice_data = self.image_data[:, slice_index, :]
        else:  # axis == 2
            slice_data = self.image_data[:, :, slice_index]

        return slice_data

    def normalize_slice(self, slice_data):
        """
        标准化切片数据
        Args:
            slice_data: 切片数据
        Returns:
            np.ndarray: 标准化后的切片数据
        """
        if slice_data is None:
            return None

        # 最小值-最大值标准化
        min_val = np.min(slice_data)
        max_val = np.max(slice_data)

        if max_val - min_val > 0:
            normalized_slice = (slice_data - min_val) / (max_val - min_val)
        else:
            normalized_slice = slice_data

        # 转换为 0-255 范围
        normalized_slice = (normalized_slice * 255).astype(np.uint8)

        return normalized_slice

    def convert_to_pil(self, slice_data):
        """
        将切片数据转换为 PIL Image
        Args:
            slice_data: 切片数据
        Returns:
            PIL.Image: PIL 图像对象
        """
        if slice_data is None:
            return None

        # 标准化切片
        normalized_slice = self.normalize_slice(slice_data)

        # 转换为 PIL Image
        pil_image = Image.fromarray(normalized_slice)

        # 调整大小为 896x896（模型要求的输入大小）
        pil_image = pil_image.resize((896, 896))

        return pil_image

    def process_image_for_model(self, slice_index, axis=2):
        """
        处理图像以适应模型输入
        Args:
            slice_index: 切片索引
            axis: 切片轴
        Returns:
            PIL.Image: 处理后的 PIL 图像对象
        """
        # 获取切片
        slice_data = self.get_slice(slice_index, axis)

        # 转换为 PIL Image
        pil_image = self.convert_to_pil(slice_data)

        return pil_image


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description="处理 nii.gz 格式的医学影像")
    parser.add_argument("image_path", type=str, help="nii.gz 文件路径")
    parser.add_argument("slice_index", type=int, help="切片索引")
    parser.add_argument("--axis", type=int, default=2, help="切片轴 (0, 1, 2)")

    args = parser.parse_args()

    # 创建预处理器实例
    preprocessor = ImagePreprocessor(args.image_path)

    # 加载图像
    if preprocessor.load_image():
        # 处理图像
        pil_image = preprocessor.process_image_for_model(args.slice_index, args.axis)

        if pil_image:
            # 保存处理后的图像
            output_path = (
                os.path.splitext(os.path.basename(args.image_path))[0]
                + f"_slice_{args.slice_index}.png"
            )
            pil_image.save(output_path)
            print(f"处理后的图像已保存到: {output_path}")
        else:
            print("图像处理失败")
    else:
        print("图像加载失败")
