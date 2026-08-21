Page({

  data: {

    confirmed: false

  },


  checkboxChange(e) {

    const checked = e.detail.value.length > 0

    this.setData({
      confirmed: checked
    })

  },


  goExam() {

    if (!this.data.confirmed) {

      wx.showToast({
        title: "请先确认已阅读安全须知",
        icon: "none"
      })

      return

    }


    wx.showToast({
      title: "即将进入测验",
      icon: "none"
    })


    /*
      下一步：

      跳转到 exam 页面

      wx.navigateTo({
        url: '/pages/exam/exam'
      })
    */

  }

})