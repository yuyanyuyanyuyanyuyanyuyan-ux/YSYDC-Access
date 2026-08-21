Page({

  data: {

    // 是否确认已经阅读安全须知
    confirmed: false

  },


  // 监听复选框变化
  checkboxChange(e) {

    const checked = e.detail.value.length > 0

    this.setData({
      confirmed: checked
    })

  },


  // 进入测验
  goExam() {

    // 判断用户是否勾选确认
    if (!this.data.confirmed) {

      wx.showToast({
        title: "请先确认已阅读安全须知",
        icon: "none"
      })

      return

    }


    // 跳转到在线测验页面
    wx.navigateTo({
      url: '/pages/exam/exam'
    })

  }

})