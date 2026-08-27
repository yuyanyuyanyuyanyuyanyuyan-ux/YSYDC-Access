Page({
  goVisitor() {
    wx.navigateTo({
      url: '/pages/visitor-login/visitor-login'
    })
  },
  goBusiness() {
    wx.navigateTo({
      url: '/pages/business-login/business-login'
    })
  }
})
