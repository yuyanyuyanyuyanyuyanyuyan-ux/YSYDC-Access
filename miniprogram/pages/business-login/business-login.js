Page({
  data: {
    username: '',
    password: ''
  },

  inputUsername(e) {
    this.setData({ username: e.detail.value })
  },

  inputPassword(e) {
    this.setData({ password: e.detail.value })
  },

  login() {
    const { username, password } = this.data
    if (!username.trim() || !password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' })
      return
    }
    wx.showLoading({ title: '登录中' })
    wx.request({
      url: 'http://127.0.0.1:8000/api/business/login',
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { username, password },
      success: (res) => {
        if (res.data.success) {
          wx.setStorageSync('business_token', res.data.token)
          wx.setStorageSync('business_member', res.data.member)
          wx.redirectTo({ url: '/pages/business-home/business-home' })
        } else {
          wx.showToast({ title: res.data.message || '登录失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/business-register/business-register' })
  }
})
