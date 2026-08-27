Page({
  data: {
    visitor: null,
    status: '未预约'
  },

  onShow() {
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.reLaunch({ url: '/pages/visitor-login/visitor-login' })
      return
    }
    this.setData({ visitor: wx.getStorageSync('visitor') })
    this.loadStatus()
  },

  loadStatus() {
    const userId = wx.getStorageSync('user_id')
    wx.request({
      url: `http://127.0.0.1:8000/api/visitor/status/${userId}`,
      method: 'GET',
      success: (res) => {
        if (res.data.success) {
          this.setData({ status: res.data.status })
        }
      }
    })
  },

  startExam() {
    const status = this.data.status
    if (status === '审批通过' || status === '预约成功') {
      wx.navigateTo({ url: '/pages/safety/safety' })
    } else if (status === '未预约' || status === '审批未通过') {
      wx.showModal({
        title: '提示',
        content: '您当前未获得准入资格，可先进行快速预约。',
        confirmText: '去预约',
        success: (res) => {
          if (res.confirm) this.goReserve()
        }
      })
    } else {
      wx.showToast({ title: '请等待审批完成', icon: 'none' })
    }
  },

  goReserve() {
    wx.navigateTo({ url: '/pages/visitor-reserve/visitor-reserve' })
  }
})
