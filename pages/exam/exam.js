Page({

  
  data: {

    // 当前题目编号
    currentIndex: 0,

    // 进度条宽度
    progressWidth: '10%',

    // 剩余时间：5分钟 = 300秒
    remainingTime: 300,

    // 格式化后的时间
    formattedTime: '05:00',

    // 用户答案
    answers: {},

    // 是否已经提交
    submitted: false,

    // 模拟题目
    questions: [

      {
        id: 1,
        title: '进入数据机房前，以下哪项操作是正确的？',
        options: [
          'A. 未经允许自行进入机房',
          'B. 完成安全准入测验并获得审批',
          'C. 跟随其他人员直接进入',
          'D. 使用他人门禁进入'
        ]
      },

      {
        id: 2,
        title: '进入数据机房时，应当如何管理随身物品？',
        options: [
          'A. 随意携带',
          'B. 根据机房管理规定进行检查和管理',
          'C. 可以携带任何危险物品',
          'D. 不需要检查'
        ]
      },

      {
        id: 3,
        title: '发现机房内设备出现异常时，正确的做法是？',
        options: [
          'A. 自行拆卸设备',
          'B. 拔掉所有电源',
          'C. 立即通知机房管理人员',
          'D. 忽略异常'
        ]
      },

      {
        id: 4,
        title: '未经授权，是否可以操作机房服务器设备？',
        options: [
          'A. 可以',
          'B. 不可以',
          'C. 任何情况下都可以',
          'D. 只要设备没有人使用就可以'
        ]
      },

      {
        id: 5,
        title: '进入数据机房后，应遵守哪项规定？',
        options: [
          'A. 保持机房整洁',
          'B. 随意饮食',
          'C. 大声喧哗',
          'D. 随意移动设备'
        ]
      },

      {
        id: 6,
        title: '发生火灾等紧急情况时，应首先？',
        options: [
          'A. 保持冷静并按照应急流程处理',
          'B. 随意关闭所有设备',
          'C. 继续正常工作',
          'D. 不通知任何人员'
        ]
      },

      {
        id: 7,
        title: '是否可以将机房门禁权限借给其他人员？',
        options: [
          'A. 可以',
          'B. 不可以',
          'C. 认识的人可以',
          'D. 临时借用可以'
        ]
      },

      {
        id: 8,
        title: '机房内发现异常人员时，应当？',
        options: [
          'A. 不予理会',
          'B. 与其发生冲突',
          'C. 通知机房管理人员',
          'D. 自行驱赶'
        ]
      },

      {
        id: 9,
        title: '进入机房进行操作前，应当确认？',
        options: [
          'A. 是否获得相应授权',
          'B. 是否带了手机',
          'C. 是否认识其他工作人员',
          'D. 是否穿着便装'
        ]
      },

      {
        id: 10,
        title: '完成机房相关操作后，应当？',
        options: [
          'A. 直接离开',
          'B. 按照规定完成登记和确认',
          'C. 不关闭任何设备',
          'D. 不通知任何人员'
        ]
      }

    ]
  },

  onLoad() {

    // 启动倒计时
    this.startTimer()

  },

  // 页面卸载时清除定时器
  onUnload() {

    if (this.timer) {
      clearInterval(this.timer)
    }

  },

  // 开始倒计时
  startTimer() {

    this.timer = setInterval(() => {

      let remainingTime = this.data.remainingTime - 1

      // 时间到了
      if (remainingTime <= 0) {

        remainingTime = 0

        clearInterval(this.timer)

        this.setData({
          remainingTime: 0,
          formattedTime: '00:00'
        })

        wx.showToast({
          title: '考试时间结束',
          icon: 'none'
        })

        // 自动提交
        setTimeout(() => {
          this.submitExam()
        }, 1000)

        return
      }

      const minute = Math.floor(remainingTime / 60)

      const second = remainingTime % 60

      const formattedTime =
        String(minute).padStart(2, '0') +
        ':' +
        String(second).padStart(2, '0')

      this.setData({
        remainingTime,
        formattedTime
      })

    }, 1000)

  },

  // 选择答案
  selectAnswer(e) {

    const optionIndex = e.currentTarget.dataset.index

    const currentQuestion =
      this.data.questions[this.data.currentIndex]

    const questionId = currentQuestion.id

    const answers = {
      ...this.data.answers
    }

    answers[questionId] = optionIndex

    this.setData({
      answers
    })

  },

  // 更新进度条
  updateProgress() {

    const total = this.data.questions.length

    const progressWidth =
      ((this.data.currentIndex + 1) / total) * 100 + '%'

    this.setData({
      progressWidth
    })

  },

  // 上一题
  previousQuestion() {

    if (this.data.currentIndex === 0) {
  
      wx.showToast({
        title: '已经是第一题',
        icon: 'none'
      })
  
      return
    }
  
    this.setData({
      currentIndex: this.data.currentIndex - 1
    })
  
    this.updateProgress()
  
  },

  // 下一题
  nextQuestion() {

    const total = this.data.questions.length
  
    if (this.data.currentIndex >= total - 1) {
  
      wx.showToast({
        title: '已经是最后一题',
        icon: 'none'
      })
  
      return
    }
  
    this.setData({
      currentIndex: this.data.currentIndex + 1
    })
  
    this.updateProgress()
  
  },

  // 提交考试
  submitExam() {

    if (this.data.submitted) {
      return
    }

    const answeredCount =
      Object.keys(this.data.answers).length

    const total =
      this.data.questions.length

    // 检查是否有未答题目
    if (answeredCount < total) {

      wx.showModal({

        title: '提示',

        content:
          `还有 ${total - answeredCount} 道题未完成，确定提交吗？`,

        success: (res) => {

          if (res.confirm) {
            this.confirmSubmit()
          }

        }

      })

      return
    }

    this.confirmSubmit()

  },

  // 确认提交
  confirmSubmit() {

    if (this.timer) {
      clearInterval(this.timer)
    }

    this.setData({
      submitted: true
    })

    console.log('用户答案：', this.data.answers)

    /*
      后端开发完成后，这里将发送：

      {
        userId: xxx,
        answers: {
          1: 1,
          2: 2,
          ...
        }
      }

      到本地服务器。

      分数计算不在小程序完成，
      而是在后端完成。
    */

    wx.showModal({

      title: '提交成功',

      content: '测验已提交，正在等待后台处理。',

      showCancel: false,

      success: () => {

        wx.redirectTo({
          url: '/pages/index/index'
        })

      }

    })

  }

})