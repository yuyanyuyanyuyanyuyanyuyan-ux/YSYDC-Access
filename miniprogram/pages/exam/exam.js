Page({

  data: {

    // 当前题目编号
    currentIndex: 0,

    // 进度条宽度
    progressWidth: '0%',

    // 剩余时间：5分钟 = 300秒
    remainingTime: 300,

    // 格式化后的时间
    formattedTime: '05:00',

    // 用户答案
    answers: {},

    // 是否已经提交
    submitted: false,

    // 考试题目
    questions: []

  },


  // 页面加载

  onLoad() {

    // 从后端加载考试题目
    this.loadQuestions()

  },


  // 从后端获取考试题目

  loadQuestions() {

    wx.showLoading({
      title: '加载题目中'
    })


    wx.request({

      // 本地 FastAPI 服务器
      url: 'http://127.0.0.1:8000/api/questions',

      method: 'GET',


      // 请求成功

      success: (response) => {

        console.log(
          '获取题目结果：',
          response.data
        )


        // 判断后端是否返回成功

        if (
          response.data.success &&
          response.data.questions &&
          response.data.questions.length > 0
        ) {

          /*
            将数据库返回的数据：

            {
              id,
              question,
              option_a,
              option_b,
              option_c,
              option_d
            }

            转换成当前小程序使用的：

            {
              id,
              title,
              options
            }
          */

          const questions =
            response.data.questions.map(item => {

              return {

                id: item.id,

                title: item.question,

                options: [

                  'A. ' + item.option_a,

                  'B. ' + item.option_b,

                  'C. ' + item.option_c,

                  'D. ' + item.option_d

                ]

              }

            })


          // 保存题目

          this.setData({

            questions: questions,

            // 从第一题开始
            currentIndex: 0,

            // 初始化进度条
            progressWidth:
              (1 / questions.length * 100) + '%'

          })


          console.log(
            '题目加载成功：',
            questions
          )


          // 题目加载完成后开始倒计时

          this.startTimer()

        } else {

          wx.showToast({

            title: '没有获取到考试题目',

            icon: 'none'

          })

        }

      },


      // 请求失败

      fail: (error) => {

        console.error(
          '获取题目失败：',
          error
        )


        wx.showToast({

          title: '无法连接后端服务器',

          icon: 'none'

        })

      },


      // 请求完成

      complete: () => {

        wx.hideLoading()

      }

    })

  },


  // 页面卸载时清除定时器

  onUnload() {

    if (this.timer) {

      clearInterval(this.timer)

    }

  },


  // 开始倒计时

  startTimer() {

    // 防止重复创建定时器

    if (this.timer) {

      clearInterval(this.timer)

    }


    this.timer = setInterval(() => {

      let remainingTime =
        this.data.remainingTime - 1


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


      // 计算分钟

      const minute =
        Math.floor(remainingTime / 60)


      // 计算秒

      const second =
        remainingTime % 60


      // 格式化时间

      const formattedTime =

        String(minute).padStart(2, '0') +

        ':' +

        String(second).padStart(2, '0')


      // 更新页面

      this.setData({

        remainingTime,

        formattedTime

      })

    }, 1000)

  },


  // 选择答案

  selectAnswer(e) {

    const optionIndex =
      e.currentTarget.dataset.index


    const currentQuestion =

      this.data.questions[
        this.data.currentIndex
      ]


    // 当前题目 ID

    const questionId =
      currentQuestion.id


    // 复制原来的答案

    const answers = {

      ...this.data.answers

    }


    // 保存用户选择

    answers[questionId] =
      optionIndex


    this.setData({

      answers

    })


    console.log(
      '当前用户答案：',
      answers
    )

  },


  // 更新进度条

  updateProgress() {

    const total =
      this.data.questions.length


    // 防止题目为空

    if (total === 0) {

      return

    }


    const progressWidth =

      (
        (this.data.currentIndex + 1)

        / total

      ) * 100 + '%'


    this.setData({

      progressWidth

    })

  },


  // 上一题

  previousQuestion() {

    // 如果已经是第一题

    if (
      this.data.currentIndex === 0
    ) {

      wx.showToast({

        title: '已经是第一题',

        icon: 'none'

      })


      return

    }


    // 切换到上一题

    this.setData({

      currentIndex:
        this.data.currentIndex - 1

    })


    // 更新进度条

    this.updateProgress()

  },


  // 下一题

  nextQuestion() {

    const total =
      this.data.questions.length


    // 如果已经是最后一题

    if (
      this.data.currentIndex
      >= total - 1
    ) {

      wx.showToast({

        title: '已经是最后一题',

        icon: 'none'

      })


      return

    }


    // 切换到下一题

    this.setData({

      currentIndex:
        this.data.currentIndex + 1

    })


    // 更新进度条

    this.updateProgress()

  },


  // 提交考试

  submitExam() {

    // 防止重复提交

    if (
      this.data.submitted
    ) {

      return

    }


    // 已答题数量

    const answeredCount =

      Object.keys(
        this.data.answers
      ).length


    // 总题目数量

    const total =

      this.data.questions.length


    // 检查是否有未答题目

    if (
      answeredCount < total
    ) {

      wx.showModal({

        title: '提示',

        content:

          `还有 ${
            total - answeredCount
          } 道题未完成，确定提交吗？`,


        success: (res) => {

          if (
            res.confirm
          ) {

            this.confirmSubmit()

          }

        }

      })


      return

    }


    // 所有题目已经完成

    this.confirmSubmit()

  },


  // 确认提交

  // 确认提交

// 确认提交考试

confirmSubmit() {

  // =========================
  // 停止倒计时
  // =========================

  if (this.timer) {

    clearInterval(this.timer)

  }


  // =========================
  // 获取登记时保存的用户 ID
  // =========================

  const userId = wx.getStorageSync('user_id')


  console.log(
    '当前获取到的用户 ID：',
    userId
  )


  // =========================
  // 判断是否获取到用户信息
  // =========================

  if (!userId) {

    wx.showToast({

      title: '未获取到用户信息',

      icon: 'none'

    })

    return

  }


  // =========================
  // 防止重复提交
  // =========================

  this.setData({

    submitted: true

  })


  // =========================
  // 显示提交状态
  // =========================

  wx.showLoading({

    title: '正在提交考试'

  })


  // =========================
  // 向后端提交考试答案
  // =========================

  wx.request({

    url: 'http://127.0.0.1:8000/api/submit-exam',

    method: 'POST',

    header: {

      'content-type': 'application/json'

    },


    data: {

      user_id: userId,

      answers: this.data.answers

    },


    // =========================
    // 请求成功
    // =========================

    success: (response) => {

      console.log(

        '考试提交结果：',

        response.data

      )


      if (response.data.success) {


        const score = response.data.score

        const passed = response.data.passed


        // =========================
        // 考试通过
        // =========================

        if (passed) {

          wx.showModal({

            title: '考试通过',

            content:
              `您的考试成绩为 ${score} 分，已生成准入凭证。`,

            showCancel: false,


            success: () => {

              wx.redirectTo({

                url: '/pages/credential/credential'

              })

            }

          })

        }


        // =========================
        // 考试未通过
        // =========================

        else {

          wx.showModal({

            title: '考试未通过',

            content:
              `您的考试成绩为 ${score} 分，未达到 70 分。`,

            showCancel: false,


            success: () => {

              wx.redirectTo({

                url: '/pages/index/index'

              })

            }

          })

        }

      }


      // =========================
      // 后端返回失败
      // =========================

      else {

        wx.showToast({

          title:
            response.data.message || '考试提交失败',

          icon: 'none'

        })


        // 提交失败后允许重新提交

        this.setData({

          submitted: false

        })

      }

    },


    // =========================
    // 网络请求失败
    // =========================

    fail: (error) => {

      console.error(

        '提交考试失败：',

        error

      )


      wx.showToast({

        title: '无法连接服务器',

        icon: 'none'

      })


      // 恢复提交状态

      this.setData({

        submitted: false

      })

    },


    // =========================
    // 请求完成
    // =========================

    complete: () => {

      wx.hideLoading()

    }

  })

}

})