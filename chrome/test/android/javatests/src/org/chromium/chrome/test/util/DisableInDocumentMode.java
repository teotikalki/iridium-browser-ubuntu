// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package org.chromium.chrome.test.util;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

/**
 * This annotation can be used to mark a test that should be disabled in Document mode.
 */
@Retention(RetentionPolicy.RUNTIME)
public @interface DisableInDocumentMode {
};
