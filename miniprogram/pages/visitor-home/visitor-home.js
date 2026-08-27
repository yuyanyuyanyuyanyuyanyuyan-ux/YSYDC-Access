Page({
  data: {
    visitor: null
  },

  onShow() {
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.reLaunch({ url: '/pages/visitor-login/visitor-login' })
      return
    }
    this.setData({ visitor: wx.getStorageSync('visitor') })
  },

  startExam() {
    wx.navigateTo({ url: '/pages/safety/safety' })
  }
})
