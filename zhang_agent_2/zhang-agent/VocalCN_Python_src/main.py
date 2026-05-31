import os
import sys
import struct
import pypinyin
import wave
import re
from datetime import datetime

# 声母韵母
characters = ['b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h', 'j', 'q', 'x',
              'zh', 'ch', 'sh', 'r', 'z', 'c', 's', 'y', 'w',
              'a', 'o', 'e', 'i', 'u', 'ü', 'ai', 'ei', 'ui', 'ao', 'ou', 'iu', 'ie', 've', 'er',
              'an', 'en', 'in', 'un', 'ün', 'ang', 'eng', 'ing', 'ong',
              'uang', 'uan', 'uai', 'uo', 'ua', 'ia', 'ian', 'iang', 'iong', 'iao']
yun_mu_list = ['a', 'o', 'e', 'i', 'u', 'ü', 'ai', 'ei', 'ui', 'ao', 'ou', 'iu', 'ie', 've', 'er',
               'an', 'en', 'in', 'un', 'ün', 'ang', 'eng', 'ing', 'ong',
               'uang', 'uan', 'uai', 'uo', 'ua', 'ia', 'ian', 'iang', 'iong', 'iao']


def get_resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


script_directory = get_resource_path('')

# 先读一个音频，获取参数信息
file = wave.open(script_directory + '/resources/a.wav', 'rb')
channels = file.getnchannels()
sampleWidth = file.getsampwidth()
sampleRate = file.getframerate()

compType = "NONE"
compName = "not compressed"
file.close()

# 模式，0全读，1动森
mode = 0
# 动森模式下，每句最多读的字符数
dong_sen_max = 8
# 韵母从声母的什么位置开始加入
secondPosition = 0.5
# 空白符的停顿时间
blankDuration = 0.2
# 两个字符衔接时，后一个字符从前一个字符还剩多少时间时切入
connectionPosition = 0.005
connectionSamples = round(connectionPosition * sampleRate)

# 是否生成过程发生错误
isWrong = False
# 是否过载
isOverload = False

# 提示语
str_notice = '1、空格会被自动去除。\n' \
             '2、其他所有非中文字符会被视为停顿。\n' \
             '3、更改模式输入数字“0：全读模式，1：动森模式”。\n' \
             '4、动森模式为断出的每个单句最多读8个字符，用|符号断句，超出时只平均地挑取出不超量的字符。\n' \
             '5、退出输入数字2。'

# 读取所有音频的采样点数据
characters_sound = {}
for c in characters:
    file = wave.open(script_directory + '/resources/' + c + '.wav', 'rb')
    samples = file.readframes(file.getnframes())
    sampleWidth = file.getsampwidth()
    # 把二进制字符串，按位深度，逐个采样点转为int，以便计算
    samplesByInt = []
    for i in range(0, len(samples), sampleWidth):
        samplesByInt.append(struct.unpack('h', samples[i:i + sampleWidth])[0])
    characters_sound[c] = samplesByInt
    file.close()


# 获取时间
def get_time():
    current_datetime = datetime.now()
    current_time = current_datetime.time()
    current_time = current_time.replace(microsecond=0)
    return str(current_time)


# 文字转拼音
def get_pinyin(text):
    return pypinyin.slug(text, separator=' ')


# 分割为拼音+标点列表
def get_py_list(pinyin: str):
    return pinyin.split(' ')


# list长度超出max时，平均的取值不超量个元素组成新list
def average_sublist(lst, val_max):
    sublist_size = len(lst) // val_max
    remainder = len(lst) % val_max
    result = []
    start = 0
    for _ in range(val_max):
        end = start + sublist_size
        if remainder > 0:
            end += 1
            remainder -= 1
        result.append(lst[start])
        start = end
    return result


# 处理输入
def handle_input(text: str):
    global isWrong
    pinyin = get_pinyin(text)
    py_list = get_py_list(pinyin)
    if len(py_list) == 0:
        print('输入有误')
        isWrong = True
        return []
    # 用来拼接新音频
    audio = []
    # 如果是动森模式，要判断长度是否超出，超出时平均取出不超量的字符。
    if mode == 1:
        if len(py_list) > dong_sen_max:
            # 先找出最后一个口头禅
            last_word = ''
            for cha in reversed(py_list):
                if cha[0].isalpha():
                    last_word = cha
                    break
            # 平均取出不超量的字符
            py_list = average_sublist(py_list, dong_sen_max)
            # 如果最后一个口头禅缺失，加上
            if py_list[-1] != last_word:
                py_list.append(last_word)
    # 上一个字符是否是拼音
    last_cha_ispy = False
    # 逐个字符处理
    for cha in py_list:
        # 储存单字符
        word = []
        # 检查是符号还是拼音
        if cha[0].isalpha():
            # 处理单韵母
            if cha in yun_mu_list:
                sheng_mu = None
                yun_mu = cha
            else:
                sheng_mu = cha[0]
                yun_mu = cha[1:]
            # 处理卷舌音声母
            if sheng_mu and yun_mu[0] == 'h':
                yun_mu = cha[2:]
                sheng_mu = sheng_mu + 'h'
            # 处理ü
            if cha == 'nv' or cha == 'lv' or cha == 'ju' or cha == 'qu' or cha == 'xu' or cha == 'yu':
                yun_mu = 'ü'
            elif cha == 'jun' or cha == 'qun' or cha == 'xun' or cha == 'yun':
                yun_mu = 'ün'
            elif cha == 'xue' or cha == 'jue' or cha == 'que' or cha == 'yue':
                yun_mu = 've'
            if sheng_mu and sheng_mu not in characters:
                print('没有找到对应声母：' + sheng_mu)
                isWrong = True
                return []
            if yun_mu not in characters:
                print('没有找到对应韵母：' + yun_mu)
                isWrong = True
                return []
            sheng_mu_samples = []
            if sheng_mu:
                sheng_mu_samples = characters_sound[sheng_mu]
            yun_mu_samples = characters_sound[yun_mu]
            yun_mu_position = 0
            if sheng_mu:
                yun_mu_position = round(len(sheng_mu_samples) * secondPosition)
            # 该字符的采样点总数
            cha_length = yun_mu_position + len(yun_mu_samples)
            for idx in range(cha_length):
                # 拼合点之前
                if idx < yun_mu_position:
                    word.append(sheng_mu_samples[idx])
                # 拼合点之后
                else:
                    a = 0
                    b = 0
                    if sheng_mu and idx < len(sheng_mu_samples):
                        a = sheng_mu_samples[idx]
                    if idx - yun_mu_position < len(yun_mu_samples):
                        b = yun_mu_samples[idx - yun_mu_position]
                    word.append(a + b)
            # 如果上一个字符也是拼音，涉及到衔接点
            if last_cha_ispy and len(audio) >= connectionSamples:
                if len(word) >= connectionSamples:
                    word_first_part = word[:connectionSamples]
                    word_second_part = word[connectionSamples:]
                else:
                    word_first_part = word
                    word_second_part = []
                # 从上一个字符的拼接处开始拼接
                for idx in range(len(audio) - connectionSamples, len(audio)):
                    if len(word_first_part) > idx:
                        audio[idx] = audio[idx] + word_first_part[idx - len(audio) + connectionSamples]
                    else:
                        break
                audio.extend(word_second_part)
            else:
                audio.extend(word)
            last_cha_ispy = True
        else:
            blank_num = round(sampleRate * len(cha) * blankDuration)
            audio.extend([0] * blank_num)
            last_cha_ispy = False
    return audio


# 储存文件
def save_file(audio, text):
    global isOverload
    front_name = text.replace(' ', '')
    if len(text) > 3:
        front_name = text[:3]
    output_name = get_time().replace(':', '_') + '_' + front_name
    output_dir = get_resource_path('output')

    # Create the output directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    path = os.path.join(output_dir, output_name + '.wav')
    output_file = wave.open(path, 'wb')
    frames = len(audio)
    output_file.setparams((channels, sampleWidth, sampleRate, frames, compType, compName))
    for sample in audio:
        resample = sample
        if sample > 32767:
            resample = 32767
            isOverload = True
        elif sample < -32768:
            resample = -32768
            isOverload = True
        output_file.writeframes(struct.pack('h', resample))
    output_file.close()


def main():
    global mode
    global isWrong
    global isOverload
    print(str_notice)
    if mode == 0:
        print('当前是全读模式。')
    else:
        print('当前是动森模式。')
    while True:
        isWrong = False
        isOverload = False
        user_input = input('请输入：')
        # 去掉空格
        user_input = user_input.replace(' ', '')
        # 去掉字母
        user_input = re.sub(r'[a-zA-Z]', '!', user_input)
        if user_input == '2':
            sys.exit(0)
        elif user_input == '0':
            mode = 0
            print('已切换为全读模式。')
            continue
        elif user_input == '1':
            mode = 1
            print('已切换为动森模式。')
            continue
        elif user_input == '':
            print('输入有误！')
            continue
        else:
            audio = []
            # 如果是动森模式，要断句
            if mode == 1:
                lists = user_input.split('|')
                for idx in range(len(lists)):
                    sentence = handle_input(lists[idx])
                    audio.extend(sentence)
            else:
                audio = handle_input(user_input)
            if not isWrong and audio and len(audio) > 0:
                save_file(audio, user_input)
                if isOverload:
                    print('发生了过载削波，可能造成一些失真，可尝试降低resource里的音频资源的平均响度。')
                print('生成成功！')
            else:
                print('生成错误！', user_input)


main()