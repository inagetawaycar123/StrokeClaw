import nibabel as nib
import numpy as np
from PIL import Image


class NIIProcessor:
    @staticmethod
    def get_nii_info(filepath):
        """获取NIfTI文件信息"""
        try:
            img = nib.load(filepath)
            data = img.get_fdata()

            info = {
                "shape": data.shape,
                "data_type": str(data.dtype),
                "data_range": [float(data.min()), float(data.max())],
                "voxel_dims": img.header.get_zooms()[:3],
                "affine": img.affine.tolist(),
            }

            return info
        except Exception as e:
            raise Exception(f"读取NIfTI文件失败: {str(e)}")

    @staticmethod
    def convert_to_png(slice_data, method="percentile"):
        """
        将切片数据转换为PNG

        参数:
            slice_data: 切片数据
            method: 转换方法 ('percentile', 'full_range', 'manual')
        """
        # 处理NaN和无限值
        slice_data = np.nan_to_num(slice_data)

        if method == "percentile":
            # 百分位方法（推荐）
            low_val = np.percentile(slice_data, 2)
            high_val = np.percentile(slice_data, 98)
        elif method == "full_range":
            # 完整范围方法
            low_val = slice_data.min()
            high_val = slice_data.max()
        else:
            # 手动方法
            low_val = np.percentile(slice_data, 5)
            high_val = np.percentile(slice_data, 95)

        # 避免除零
        if high_val - low_val < 1e-6:
            low_val = slice_data.min()
            high_val = slice_data.max()
            if high_val - low_val < 1e-6:
                low_val = 0
                high_val = 1

        # 剪切和归一化
        data_clipped = np.clip(slice_data, low_val, high_val)
        data_normalized = (data_clipped - low_val) / (high_val - low_val)
        data_8bit = (data_normalized * 255).astype(np.uint8)

        return data_8bit

    @staticmethod
    def extract_all_slices(nii_path):
        """提取所有切片"""
        img = nib.load(nii_path)
        data = img.get_fdata()

        slices = []
        num_slices = data.shape[2] if len(data.shape) >= 3 else 1

        for i in range(num_slices):
            if len(data.shape) == 3:
                slice_data = data[:, :, i]
            elif len(data.shape) == 4:
                slice_data = data[:, :, i, 0]
            else:
                slice_data = data

            slices.append(slice_data)

        return slices
