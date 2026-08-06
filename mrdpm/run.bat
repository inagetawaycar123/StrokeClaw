python run.py -c config/npy_1000linear_-6_-2_b4_nc64.json -gpu 0 -p test

python L_alone.py --input /home/public/MRDPM-with-RAP-main/experiments/train_mCTA2CTP_251120_234757/results/val/1/Out_01-049_14.npy --output /home/public/MRDPM-with-RAP-main/Out_01-049_14_2.png

 -i https://pypi.tuna.tsinghua.edu.cn/simple

 python test_predictor.py --config G:\2\MRDPM-with-RAP-main\config\npy_1000linear_-6_-2_b4_nc64.json --model G:\NeuroMatrix_AI\weights_mrdpm\tmax\bran_pretrained_3channel.pth --output G:\test_pretrain_tmax